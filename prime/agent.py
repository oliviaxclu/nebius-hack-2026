"""Tool-calling agent loop + deterministic guardrails that do NOT depend on the model behaving."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime

from . import cites
from .tools import TOOL_SCHEMAS, Toolbox

SYSTEM = """You are Prime, a private, voice-first assistant that helps one person with diabetes understand THEIR OWN glucose, insulin, meals, medicines and sleep, and prepare for clinic visits.

About this person (from their accessibility profile):
{profile}

How to talk:
- Plain, short sentences. Lead with the single most important point. At most three points, then offer to continue.
- Say numbers and times plainly. Never say "see the chart", "as shown", or refer to colors or positions on a screen. The person may only hear you.
- Say dates and times the way people speak: "Oct 19 at 3 AM", never "2026-10-19 03:00". Dates appear only inside citation ids.
- Never use internal names of tools or fields (such as check_dose_response or possible_compression_artifact). Say "possible sensor error", "the insulin check". Explain any medical term in a few words.
- When you log a dose or a meal, read it back. 

Rules you always follow:
1. You are not a clinician. Never diagnose. NEVER tell the person to take, skip, double, repeat, increase or decrease any medicine, and never give a number of units to take. If asked, say you cannot advise on doses and point to their care team or pharmacist.
2. For "why" questions, call get_episode_context and search_medical_evidence. Give the most likely explanations in order, what in THEIR data supports each, and what would tell them apart. Be honest about uncertainty. Mention the evidence level when it matters. Do not present consumer or news sources as guidelines. Pregnancy hormones apply to gestational diabetes only.
3. If mornings are high despite logged insulin, or they ask whether insulin is working, call check_dose_response. Report its competing hypotheses honestly. Never conclude that insulin was not delivered; say the pattern is unusual compared with their own reference days, list what to check, and follow the tool's safe next steps, including contacting the care team today when it flags a pattern.
4. If they are about to inject, or ask how to use the pen, call pre_injection_checklist and walk through one or two steps at a time. Then log the dose with log_insulin. If log_insulin returns a warning, say it first and plainly and do not continue.
   For where to inject, call get_injection_sites: suggest its next spot, say its checks, and say its overuse warning first if there is one. After they inject, record the spot with log_injection_site.
5. A low from the sensor that is flagged possible_compression_artifact should be confirmed with a fingerstick before treating. A low with symptoms is real. Emergencies: tell them to call emergency services now.
6. Cite every fact about their data or the evidence with the ids from tool results in square brackets, like [day:2026-10-01], [ins:12], [meal:7], [ste:3], [site:4], [src:1a2b3c4d]. Never invent an id. If data is missing, say so.
7. Save notes with add_journal. Create reminders with create_reminder using an ISO datetime.
8. Names and identifiers appear as placeholders like [PATIENT]. That is intentional.
Today is {today}."""

THINK = re.compile(r"<think>.*?</think>", re.S)

EMERGENCY = re.compile(
    r"chest pain|can'?t breathe|cannot breathe|trouble breathing|unconscious|passed out|unresponsive|seizure|stroke|face (is )?droop"
    r"|can'?t (be )?wake|won'?t wake|suicid|kill myself|want to die|end my life", re.I)
EMERGENCY_REPLY = ("This could be an emergency. Call 911 now, or your local emergency number. "
                   "If you are thinking about harming yourself, call or text 988 in the US. "
                   "If someone is with you, ask them to stay with you and make the call.")

# ---- no-dose-advice guard (applied to every final answer) ------------------------------------------
# A sentence is removed when it TELLS the person to change, take, skip or time a medicine dose: an instruction verb in
# instruction position (sentence or clause start, or after "you should", "try to", "don't"...) aimed at a dose within a
# few words. Descriptions ("lumps change how insulin is absorbed"), reports ("the dose was raised") and device steps
# ("dial 2 units for the safety test", "check that 12 units are left") are not instructions about a dose and stay.
_CUE = (r"(?:^|[.;:!?]\s+|,\s*|\b(?:and|then|you should|you could|you can|you may want to|you might want to|you need to|"
        r"you'll need to|try(?: to)?|please|consider|i would|i'd|i recommend|i suggest|we could|it's best to|go ahead and|"
        r"make sure to|be sure to|do not|don't|dont|never)\s+)")
_VERB = (r"(?:tak(?:e|ing)|inject(?:ing)?|giv(?:e|ing) yourself|dial(?:ing)?|us(?:e|ing)|add(?:ing)?|increas(?:e|ing)|rais(?:e|ing)|"
         r"bump(?:ing)?(?: up)?|go(?:ing)? up|decreas(?:e|ing)|lower(?:ing)?|reduc(?:e|ing)|cut(?:ting)?(?: back)?|drop(?:ping)?|"
         r"doubl(?:e|ing)|halv(?:e|ing)|skip(?:ping)?|stop(?:ping)?|hold(?:ing)? off(?: on)?|miss(?:ing)?|repeat(?:ing)?|"
         r"chang(?:e|ing)|adjust(?:ing)?|switch(?:ing)?(?: to)?|restart(?:ing)?)")
_QTY = r"\d+(?:\.\d+)?\s*(?:units?|u|mg|milligrams?|ml)\b"
_MED = (r"(?:insulin|doses?|shots?|injections?|units|medicine|medication|basal|bolus|lantus|toujeo|basaglar|semglee|rezvoglar|tresiba|"
        r"levemir|humalog|novolog|admelog|apidra|fiasp|lyumjev|humulin|novolin|ozempic|wegovy|mounjaro|zepbound|trulicity|victoza|saxenda)")
_OBJ = (rf"(?:{_QTY}|\d+\s+(?:more|less|extra|fewer)\s+{_MED}|(?:more|less|extra|fewer|another|an extra|a bigger|a smaller|half)\s+(?:\w+\s+)?{_MED}|"
        rf"(?:your|tonight's|today's|tomorrow's|this evening's|this week's|next week's|this|next|the next)\s+(?:\w+\s+){{0,2}}{_MED})")
_DIRECTIVE = re.compile(rf"{_CUE}{_VERB}\b(?:\W+\w+){{0,3}}?\W+{_OBJ}", re.I)
_PRESCRIBE = re.compile(r"\b(?:your|the)\s+(?:\w+\s+)?doses?\s+(?:should|would|could|needs? to|ought to)\s+(?:be|go)\b"
                        r"(?:\W+\w+){0,4}?\W+(?:\d|higher|lower|more|less|up|down|increased|decreased|raised|lowered|reduced|changed)", re.I)
_PRIMING = re.compile(r"\b(?:safety test|prim(?:e|ing)|flow (?:check|test)|air ?shot)\b", re.I)
_PRIME_QTY = re.compile(r"\b(?:dial|select|set|turn(?: it)? to)\s+\d+\s*units?\b", re.I)
_SAFE = re.compile(r"\b(cannot|can't|not advise|no advice|ask|talk to|talk with|contact|call|check with|confirm with|discuss|care team|clinician|"
                   r"doctor|pharmacist|educator|prescriber|prescribed|prescription|as directed)\b", re.I)
REFUSAL_SENTENCE = "I can't advise on medicine doses. Please ask your care team or pharmacist."


def is_dose_advice(sentence: str) -> bool:
    s = sentence.strip()
    if not s or _SAFE.search(s):
        return False
    if _PRIMING.search(s):                       # the safety-test amount is a device step, not a dose
        s = _PRIME_QTY.sub("", s)
    return bool(_DIRECTIVE.search(s) or _PRESCRIBE.search(s))


def enforce_no_dose_advice(text: str) -> tuple[str, list[str]]:
    """Replace any sentence that tells the user to take/change insulin with a refusal. Returns (text, removed sentences)."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    removed, out = [], []
    for s in parts:
        if is_dose_advice(s):
            removed.append(s.strip())
            if REFUSAL_SENTENCE not in out:
                out.append(REFUSAL_SENTENCE)
        else:
            out.append(s)
    return "\n".join(out).strip() if removed else text, removed


@dataclass
class AgentResult:
    text: str
    trace: list[dict] = field(default_factory=list)
    guard: dict = field(default_factory=dict)


class Agent:
    def __init__(self, llm, toolbox: Toolbox, max_steps: int = 10):
        self.llm, self.tools, self.max_steps = llm, toolbox, max_steps

    def _system(self) -> dict:
        from . import db
        prof = db.load_profile(self.tools.conn)
        lines = "\n".join(f"- {k.replace('_', ' ')}: {v}" for k, v in prof.items()) or "- (none recorded)"
        return {"role": "system", "content": SYSTEM.format(profile=lines, today=self.tools.now().strftime("%A, %Y-%m-%d, %I:%M %p"))}

    def ask(self, question: str, history: list[dict] | None = None) -> AgentResult:
        if EMERGENCY.search(question):
            if history is not None:
                history += [{"role": "user", "content": question}, {"role": "assistant", "content": EMERGENCY_REPLY}]
            return AgentResult(EMERGENCY_REPLY, [], {"emergency": True})
        messages = [self._system()] + list(history or []) + [{"role": "user", "content": question}]
        trace: list[dict] = []
        for _ in range(self.max_steps):
            msg = self.llm.chat(messages, tools=TOOL_SCHEMAS, purpose="agent")
            calls = getattr(msg, "tool_calls", None) or []
            if not calls:
                text = cites.normalize(THINK.sub("", msg.content or "").strip())
                text, removed = enforce_no_dose_advice(text)
                if history is not None:
                    history += [{"role": "user", "content": question}, {"role": "assistant", "content": text}]
                return AgentResult(text, trace, {"dose_advice_removed": removed} if removed else {})
            messages.append({"role": "assistant", "content": msg.content or "",
                             "tool_calls": [{"id": c.id, "type": "function",
                                             "function": {"name": c.function.name, "arguments": c.function.arguments}} for c in calls]})
            for c in calls:
                try:
                    args = json.loads(c.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = self.tools.dispatch(c.function.name, args)
                trace.append({"tool": c.function.name, "args": args, "result_chars": len(result)})
                messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
        return AgentResult("I couldn't finish that within my step limit. Try a narrower question.", trace)
