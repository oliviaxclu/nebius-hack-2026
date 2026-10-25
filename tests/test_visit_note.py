import json

from fastapi.testclient import TestClient

from prime import db, visit_note
from prime.config import Settings
from prime.llm import LLM
from prime.privacy import Redactor
from prime.web import create_app
from tests.conftest import TODAY, d
from tests.fakes import ScriptedClient, text_msg
from tests.test_web import factory_for, make_client

HEADS = "What the data shows\nWhat stands out\nQuestions to ask your care team\n"
NOTE = (f"What the data shows\n- Time in range was lower than the target [day:{d(5)}].\n"
        f"What stands out\n- Mornings ran high on several days even though insulin was logged [day:{d(15)}]. This is unusual and can have several causes.\n"
        "Questions to ask your care team\n- Should we look at the pen technique together?\nBring this to your care team. It is not medical advice.")


def client_with(tmp_path, reply, reason_model="nvidia/ultra-test"):
    seen = []

    def script():
        def capture(messages):
            seen.append(messages)
            return text_msg(reply)
        return [capture]
    s = Settings(home=tmp_path, api_key="k", base_url="http://x", model="nvidia/test", reason_model=reason_model)
    app = create_app(s, llm_factory=factory_for(script), root=tmp_path / "w", today=TODAY)
    return TestClient(app), seen


def test_note_is_written_by_the_reasoning_model_from_the_code_computed_summary(tmp_path):
    c, seen = client_with(tmp_path, NOTE)
    before = c.post("/api/chat", json={"message": "I have chest pain"}).json()["remaining"]
    r = c.post("/api/visit-note").json()
    assert r["text"].startswith("What the data shows") and r["model"] == "nvidia/ultra-test" and r["remaining"] == before - 1
    assert r["range"][0] < r["range"][1] and r["guard"] == {}
    sent = seen[0]
    assert sent[0]["role"] == "system" and "NEVER tell the person to take" in sent[0]["content"]
    assert '"glucose_summary"' in sent[1]["content"] and '"dose_response"' in sent[1]["content"]      # the numbers come from code, not the model
    call = c.get("/api/audit").json()["calls"][0]
    assert call["purpose"] == "visit-note" and call["model"] == "nvidia/ultra-test"


def test_thinking_is_off_and_the_model_comes_from_the_setting(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    client = ScriptedClient([text_msg("<think>hmm</think>The note.")])
    s = Settings(home=tmp_path, api_key="k", base_url="http://x", model="nvidia/test", reason_model="nvidia/ultra-test")
    out = LLM(s, conn, Redactor({}), client=client).reason([{"role": "user", "content": "hi"}])
    assert out == "The note." and client.requests[0]["model"] == "nvidia/ultra-test"
    assert client.requests[0]["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}      # Ultra over-thinks this prompt


def test_falls_back_to_the_normal_model_when_none_is_configured(tmp_path):
    c, _ = client_with(tmp_path, NOTE, reason_model="")
    assert c.post("/api/visit-note").json()["model"] == "nvidia/test"


def test_dose_advice_is_removed_and_flagged(tmp_path):
    c, _ = client_with(tmp_path, HEADS + "- Mornings ran high.\nIncrease your insulin by 2 units tonight.\nAsk your care team about the pattern.")
    r = c.post("/api/visit-note").json()
    assert "Increase your insulin" not in r["text"] and "can't advise on medicine doses" in r["text"]
    assert r["guard"]["dose_advice_removed"] and "Ask your care team" in r["text"]


def test_invented_citations_are_marked_unverified(tmp_path):
    c, _ = client_with(tmp_path, HEADS + f"- Mornings ran high [day:{d(15)}] and steroids matter [src:deadbeef] [day:2099-01-01].")
    cites = c.post("/api/visit-note").json()["citations"]
    assert cites[f"day:{d(15)}"] and cites["src:deadbeef"] is None and cites["day:2099-01-01"] is None


def test_an_empty_reply_is_an_honest_error_line_not_blank(tmp_path):
    c, _ = client_with(tmp_path, "   ")
    assert "couldn't write the note" in c.post("/api/visit-note").json()["text"]


def test_identity_never_reaches_the_model(tmp_path):
    c, seen = client_with(tmp_path, NOTE)
    c.post("/api/visit-note")
    blob = json.dumps(seen[0])
    assert "Hale" not in blob and "0172264" not in blob


def test_no_data_means_a_clear_404_and_no_model_call(tmp_path):
    conn = db.connect(tmp_path / "empty.db")
    assert visit_note.window(conn) is None


def test_budget_applies(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MAX_CALLS_PER_SESSION", "1")
    c, _ = client_with(tmp_path, NOTE)
    assert c.post("/api/visit-note").status_code == 200
    assert c.post("/api/visit-note").status_code == 429


def test_leaked_reasoning_or_a_missing_section_never_reaches_the_user(tmp_path):
    for bad in ("The user wants me to write a one-page note. Let me analyze the JSON summary and follow the rules...",
                "What the data shows\n- Only the first part was written."):
        c, _ = client_with(tmp_path / str(abs(hash(bad))), bad)
        r = c.post("/api/visit-note").json()
        assert r["text"] == visit_note.FALLBACK and r.get("failed") and "The user wants" not in r["text"]


def test_a_reply_cut_off_at_the_length_limit_is_never_returned_half_written(tmp_path):
    from types import SimpleNamespace as NS
    conn = db.connect(tmp_path / "t.db")

    class Cut(ScriptedClient):
        def create(self, **kw):
            self.requests.append(kw)
            return NS(choices=[NS(message=text_msg("What the data shows\n- half a no"), finish_reason="length")])
    s = Settings(home=tmp_path, api_key="k", base_url="http://x", model="m")
    assert LLM(s, conn, Redactor({}), client=Cut([])).reason([{"role": "user", "content": "x"}]) == ""


def test_stray_bracket_tags_are_removed_but_real_citations_stay(tmp_path):
    c, _ = client_with(tmp_path, HEADS + f"- Time in range was 68% [glucose_summary]. Lows overnight [lows] [day:{d(15)}].")
    r = c.post("/api/visit-note").json()
    assert "[glucose_summary]" not in r["text"] and "[lows]" not in r["text"] and f"[day:{d(15)}]" in r["text"]


def test_several_ids_in_one_bracket_become_separate_verified_citations(tmp_path):
    c, _ = client_with(tmp_path, HEADS + f"- Mornings ran high [day:{d(14)}, day:{d(15)}, day:2099-01-01] and lows followed [ins:1; ins:2].")
    r = c.post("/api/visit-note").json()
    assert f"[day:{d(14)}][day:{d(15)}][day:2099-01-01]" in r["text"] and "[ins:1][ins:2]" in r["text"] and ", day:" not in r["text"]
    assert r["citations"][f"day:{d(15)}"] and r["citations"]["day:2099-01-01"] is None       # still checked one by one
