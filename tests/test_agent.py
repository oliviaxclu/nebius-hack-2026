import json

from prime import cites
from prime.agent import Agent, EMERGENCY_REPLY, REFUSAL_SENTENCE, enforce_no_dose_advice
from tests.conftest import d
from tests.fakes import ScriptedLLM, call, text_msg, tool_msg


def test_agent_loop_runs_tools_strips_think_and_includes_profile(loaded):
    conn, tb, _ = loaded
    seen = {}

    def final(messages):
        seen["tool_payload"] = "\n".join(m["content"] for m in messages if m["role"] == "tool")
        seen["system"] = messages[0]["content"]
        return text_msg("<think>hm</think>Mornings were high [day:%s]. This is a pattern, not proof." % d(14))

    llm = ScriptedLLM([tool_msg(call(1, "check_dose_response", {"start": d(1), "end": d(30)}),
                                call(2, "search_medical_evidence", {"question": "steroid"})), final])
    res = Agent(llm, tb).ask("Why were my mornings high?")
    assert res.text.startswith("Mornings were high") and "<think>" not in res.text
    assert [t["tool"] for t in res.trace] == ["check_dose_response", "search_medical_evidence"]
    assert "hypotheses" in seen["tool_payload"] and "low vision" in seen["system"] and "voice first: true" in seen["system"]
    assert cites.verify(conn, res.text)[f"day:{d(14)}"]


def test_agent_normalizes_lenticular_bracket_citations(loaded):
    conn, tb, _ = loaded
    res = Agent(ScriptedLLM([text_msg("Mornings were high 【day:%s】." % d(14))]), tb).ask("Why?")
    assert res.text == "Mornings were high [day:%s]." % d(14)
    assert cites.verify(conn, res.text)[f"day:{d(14)}"]


def test_emergency_prefilter_skips_the_model(loaded):
    _, tb, _ = loaded
    llm = ScriptedLLM([])                                                      # would raise if the model were called
    for q in ("I have chest pain and feel dizzy", "I can't breathe", "he won't wake up", "I want to die"):
        res = Agent(llm, tb).ask(q)
        assert res.text == EMERGENCY_REPLY and res.guard == {"emergency": True} and "911" in res.text


def test_dose_advice_guard_removes_instructions_but_allows_safe_language():
    bad = ["Take 30 units tonight.", "You should increase your insulin dose.", "Skip your insulin tomorrow.",
           "Try to double your dose of insulin.", "Reduce your night dose by 4 units."]
    for s in bad:
        out, removed = enforce_no_dose_advice(f"Mornings were high. {s} Ask about it.")
        assert removed and s.rstrip(".") in removed[0] and REFUSAL_SENTENCE in out and s not in out, s
    good = ["Do not change or add insulin on your own.", "Ask your care team whether to change your insulin dose.",
            "Your insulin log shows 18 units each night.", "Contact your pharmacist about the pen.",
            "The insulin dose was raised on September 28.", "Insulin glargine works over about a day."]
    for s in good:
        out, removed = enforce_no_dose_advice(s)
        assert not removed and out == s, s


def test_guard_applies_to_final_answer(loaded):
    _, tb, _ = loaded
    llm = ScriptedLLM([text_msg("Your mornings were high. You should take 4 more units tonight. Please call your care team.")])
    res = Agent(llm, tb).ask("what should I do?")
    assert "4 more units" not in res.text and REFUSAL_SENTENCE in res.text and "care team" in res.text
    assert res.guard["dose_advice_removed"]


def test_step_limit_and_bad_tool_args(loaded):
    _, tb, _ = loaded
    looping = [tool_msg(call(i, "get_glucose", {"start": d(1)})) for i in range(12)]      # missing 'end' every time
    res = Agent(ScriptedLLM(looping), tb, max_steps=3).ask("loop")
    assert "step limit" in res.text and len(res.trace) == 3


def test_history_is_kept_for_chat_mode(loaded):
    _, tb, _ = loaded
    hist = []
    Agent(ScriptedLLM([text_msg("first")]), tb).ask("one", hist)
    Agent(ScriptedLLM([lambda m: text_msg("second saw %d msgs" % len(m))]), tb).ask("two", hist)
    assert [m["content"] for m in hist][:2] == ["one", "first"] and hist[-1]["content"].startswith("second saw 4")
