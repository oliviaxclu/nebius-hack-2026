import json

import pytest
from fastapi.testclient import TestClient

from prime.config import Settings
from prime.llm import LLM
from prime.web import create_app
from tests.conftest import TODAY, d
from tests.fakes import ScriptedClient, call, text_msg, tool_msg


def final_with_cites(messages):
    """Fake model: reads the check_dose_response result, then answers citing one REAL and one INVENTED source."""
    tool = next(m for m in messages if m["role"] == "tool")["content"]
    real_day = json.loads(tool)["patterns"][0]["day_cites"][0]
    return text_msg(f"Mornings ran high [{real_day}]. Steroids explain afternoons [src:deadbeef]. Ask your care team.")


def factory_for(script_fn):
    def make(settings, conn, redactor):
        return LLM(settings, conn, redactor, client=ScriptedClient(script_fn()))
    return make


def make_client(tmp_path, monkeypatch=None, script=None, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, str(v))
    script = script or (lambda: [tool_msg(call(1, "check_dose_response", {"start": d(1), "end": d(30)})), final_with_cites])
    s = Settings(home=tmp_path, api_key="k", base_url="http://x", model="nvidia/test")
    app = create_app(s, llm_factory=factory_for(script), root=tmp_path / "w", today=TODAY)
    return TestClient(app)


def test_static_and_health(tmp_path):
    c = make_client(tmp_path)
    page = c.get("/").text
    assert "Prime" in page and "Pen check" in page and 'aria-live="polite"' in page
    assert c.get("/health").json()["ok"] is True


def test_overview_has_pattern_and_highlights(tmp_path):
    c = make_client(tmp_path)
    o = c.get("/api/overview").json()
    assert len(o["days"]) == 30 and o["pattern"]["from"] == d(13) and o["pattern"]["to"] == d(20)
    assert o["pattern"]["confidence"] == "higher" and o["pattern"]["safe_next_steps"] and "risk_note" in o["pattern"]
    flagged = [x["date"] for x in o["days"] if x["flagged_morning"]]
    assert flagged == [d(n) for n in range(13, 21)]
    assert o["highlights"]["artifact"]["date"] == d(28) and o["highlights"]["deepest_low"]["nadir"] <= 54
    assert any(x["has_low"] for x in o["days"]) and o["profile"]["voice_first"] == "true"
    assert any(m["name"] == "Insulin glargine" for m in o["medications"])


def test_day_view(tmp_path):
    c = make_client(tmp_path)
    day = c.get(f"/api/day?date={d(10)}").json()
    assert len(day["points"]) == 96 and day["steroid"][0]["mg"] == 30 and len(day["meals"]) >= 3 and day["insulin"][0]["units"] == 18
    assert c.get("/api/day?date=2020-01-01").status_code == 404
    assert c.get("/api/day?date=nope").status_code == 400
    low = c.get(f"/api/day?date={d(28)}").json()
    assert any(e["possible_compression_artifact"] for e in low["excursions"])


def test_chat_verifies_citations_and_audit_is_redacted(tmp_path):
    c = make_client(tmp_path)
    r = c.post("/api/chat", json={"message": "I'm Ray Hale, MRN-0172264. Why were my mornings high?"}).json()
    assert r["trace"][0]["tool"] == "check_dose_response"
    good = {k: v for k, v in r["citations"].items() if v}
    assert len(good) == 1 and list(good)[0].startswith("day:")
    assert r["citations"]["src:deadbeef"] is None                                    # invented source flagged, not trusted
    audit = c.get("/api/audit").json()["calls"]
    assert audit[0]["replaced"].get("PATIENT") and audit[0]["replaced"].get("MRN")
    blob = json.dumps(audit)
    assert "Hale" not in blob and "0172264" not in blob and "low vision" in blob      # profile reaches the model, identity does not


def test_emergency_is_answered_without_the_model_or_budget(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, script=lambda: [], DEMO_MAX_CALLS_PER_SESSION=1)
    for _ in range(3):
        r = c.post("/api/chat", json={"message": "I have chest pain"})
        assert r.status_code == 200 and "911" in r.json()["text"]


def test_emergency_reply_works_with_no_api_key_at_all(tmp_path):
    s = Settings(home=tmp_path, api_key="", base_url="http://x", model="m")
    nokey = TestClient(create_app(s, root=tmp_path / "w3", today=TODAY))
    r = nokey.post("/api/chat", json={"message": "I have chest pain"})
    assert r.status_code == 200 and "911" in r.json()["text"] and r.json()["guard"] == {"emergency": True}
    assert nokey.post("/api/chat", json={"message": "hello"}).status_code == 503        # non-emergencies still need the model


def test_sessions_are_isolated_and_reset(tmp_path):
    a = make_client(tmp_path)
    b = TestClient(a.app)
    a.post("/api/journal", json={"body": "private note from visitor A"})
    assert any("visitor A" in j["text"] for j in a.get("/api/overview").json()["journal"])
    assert not any("visitor A" in j["text"] for j in b.get("/api/overview").json()["journal"])
    a.post("/api/reset")
    assert not any("visitor A" in j["text"] for j in a.get("/api/overview").json()["journal"])


def test_rate_limits(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch, script=lambda: [text_msg("hi"), text_msg("again")], DEMO_MAX_CALLS_PER_SESSION=1)
    assert c.post("/api/chat", json={"message": "hi"}).status_code == 200
    assert c.post("/api/chat", json={"message": "again"}).status_code == 429


def test_validation_and_missing_key(tmp_path):
    c = make_client(tmp_path)
    assert c.post("/api/chat", json={"message": ""}).status_code == 422
    assert c.post("/api/chat", json={"message": "x" * 2001}).status_code == 422
    s = Settings(home=tmp_path, api_key="", base_url="http://x", model="m")
    nokey = TestClient(create_app(s, root=tmp_path / "w2", today=TODAY))
    r = nokey.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 503 and "NEBIUS_API_KEY" in r.json()["detail"]
    assert nokey.get("/api/pen-check").status_code == 200                              # pen check needs no model


def test_every_citation_type_has_a_record_endpoint(tmp_path):
    c = make_client(tmp_path)
    for cite, kind in [(f"day:{d(14)}", "day"), ("ins:1", "ins"), ("meal:1", "meal"), ("rx:1", "rx"), ("ste:1", "ste"), ("j:1", "j")]:
        r = c.get(f"/api/record/{cite}")
        assert r.status_code == 200 and r.json()["cite"] == cite, cite
    from prime.evidence import evidence_id
    from prime.evidence_data import P
    real_src = f"src:{evidence_id(P[0]['title'])}"
    assert c.get(f"/api/record/{real_src}").json()["url"].startswith("http")
    assert c.get("/api/record/ins:99999").status_code == 404 and c.get("/api/record/src:deadbeef").status_code == 404
    assert c.get("/api/record/day:2020-01-01").status_code == 404


def test_pen_check_and_calendar(tmp_path):
    c = make_client(tmp_path)
    p = c.get("/api/pen-check").json()
    assert len(p["steps"]) == 9 and "outer cap" in json.dumps(p)          # demo pen: Lantus SoloStar, clear, so no mixing step and "inner cap" in json.dumps(p) and len(p["teach_back_questions"]) == 3
    site_step = next(s for s in p["steps"] if s.get("coach"))
    assert "two inches from your belly button" in site_step["say"] and all(site_step["src"])
    assert "BEGIN:VCALENDAR" in c.get("/calendar.ics").text
