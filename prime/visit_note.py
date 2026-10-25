"""The clinic visit note: the one job in Prime that rewards careful reasoning, so it goes to the largest Nemotron (Ultra).

Code computes every number (Toolbox.visit_summary); the model only turns that summary into a one-page note and weighs the
competing explanations. The same guards as the chat apply to what comes back: any sentence that tells the person to take or
change a medicine is replaced, and every citation is checked against the local database (unknown ones show as unverified).
"""
from __future__ import annotations

import json
import re
import sqlite3

from . import cites
from .agent import enforce_no_dose_advice

SYSTEM = """You write a one-page note that a person with diabetes brings to a clinic visit. It is built ONLY from a structured summary of THEIR OWN data, computed by code and given to you as JSON.

Write these three parts, with these exact headings:
What the data shows
- 3 to 5 short bullets with the key numbers (time in range, lows, highs). Use only numbers present in the summary.
What stands out
- The one or two things most worth a clinician's attention. If mornings are high despite logged insulin, set out the competing explanations (steroid timing, pen technique, injection-site lumps, illness, sensor problems, and a dose that may not be getting in), say what in the data supports and what argues against each, and say the pattern is unusual, not that insulin failed.
Questions to ask your care team
- 3 to 5 plain questions.

Rules you always follow:
1. You are not a clinician and this is not medical advice. NEVER tell the person to take, skip, double, repeat, increase or decrease any medicine, and never give a number of units to take. Questions for the clinician are fine.
2. Use only facts in the summary. If something is missing, say it is missing. Never invent a number, date or cause.
3. Cite a fact only with an id that appears in the summary as a "cite" or "day_cite" value (they look like day:2026-10-01, ins:12, ste:3, meal:7), in square brackets, exactly as given. Many facts have no id, such as the overall percentages and dose changes: write those with NO brackets. Never put field names like glucose_summary or lows in brackets, and never invent an id.
4. Plain, short sentences. Explain any medical term in a few words. Say dates the way people speak ("Oct 19"), and keep ids only inside the brackets.
5. Names appear as placeholders such as [PATIENT]. That is intentional.
6. End with one line: "Bring this to your care team. It is not medical advice."
Output only the note."""


def window(conn: sqlite3.Connection) -> tuple[str, str] | None:
    """The first and last day with glucose data (the note covers everything on this device)."""
    r = conn.execute("SELECT MIN(substr(ts,1,10)) a, MAX(substr(ts,1,10)) b FROM glucose").fetchone()
    return (r["a"], r["b"]) if r and r["a"] else None


def messages(summary: dict) -> list[dict]:
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Summary computed from my data (JSON):\n" + json.dumps(summary, ensure_ascii=False)}]


SECTIONS = ("What the data shows", "What stands out", "Questions to ask your care team")
FALLBACK = "I couldn't write the note this time. Try again in a moment."
# Several ids in one bracket, "[day:2026-10-07, day:2026-10-08]": split them so each one is a normal citation.
_ID = r"(?:day:\d{4}-\d{2}-\d{2}|(?:ins|meal|rx|ste|j|site):\d+|src:[0-9a-f]{8})"
_GROUP = re.compile(rf"\[\s*({_ID}(?:\s*[,;]\s*{_ID})+)\s*\]")
# A square-bracket tag that is not a real citation id (the model sometimes writes [glucose_summary] or [lows]).
_STRAY = re.compile(r"\s*\[(?!(?:day|ins|meal|rx|ste|j|site|src):)[A-Za-z_ ]+\]")


def finish(conn: sqlite3.Connection, raw: str) -> dict:
    """Apply the no-dose-advice guard and verify every citation. A reply that is empty, cut off, or missing a required section
    (for example leaked reasoning instead of a note) comes back as one honest error line, never as half a note."""
    raw = _GROUP.sub(lambda m: "".join(f"[{i.strip()}]" for i in re.split(r"[,;]", m.group(1))), (raw or "").strip())
    raw = _STRAY.sub("", raw)
    if not all(h in raw for h in SECTIONS):
        return {"text": FALLBACK, "citations": {}, "guard": {}, "failed": True}
    text, removed = enforce_no_dose_advice(raw)
    return {"text": text, "citations": cites.verify(conn, text), "guard": {"dose_advice_removed": removed} if removed else {}}
