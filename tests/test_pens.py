import json

import pytest

from prime import cites, evidence, pens, vision
from prime.pen_data import PENS
from prime.tools import TOOL_NAMES
from tests.test_web import make_client


def say_all(steps):
    return " ".join(s["say"] for s in steps)


def test_every_profile_is_sourced_and_well_formed():
    ids = [p["id"] for p in PENS]
    assert len(ids) == len(set(ids)) >= 30
    for p in PENS:
        assert p["source_url"].startswith("https://") and p["source_title"], p["id"]
        assert p["kind"] in (None, *pens.KIND_WORDS), p["id"]
        assert p["prime_units"] in (None, 2, 3, 4, 5) and p["hold_seconds"] in (None, 5, 6, 8, 10), p["id"]
        assert not p["cloudy"] or p["mix"], p["id"]                                   # a cloudy pen always says how to mix


@pytest.mark.parametrize("p", PENS, ids=lambda p: p["id"])
def test_steps_follow_the_pen(loaded, p):
    conn, tb, _ = loaded
    r = tb.pre_injection_checklist(pen=p["id"])
    text = say_all(r["steps"])
    assert r["pen"]["id"] == p["id"] and r["pen"]["hold_seconds"] == (p["hold_seconds"] or 10)
    if p["no_click_counting"]:
        assert "count the clicks" not in text and "not to set the dose by counting clicks" in text
    if p["hold_seconds"]:
        assert f"count slowly to {p['hold_seconds']} " in text
    if p["prime_units"]:
        assert f"dial {p['prime_units']} units" in text
    if p["cloudy"]:
        assert "Mix it:" in text
    if p["cloudy"] is False:
        assert "roll" not in text.lower() and "Mix it" not in text
    if p["low_vision_warning"]:
        assert "trained, sighted person" in r["steps"][0]["say"]
    for s in p["extra_steps"]:
        assert s.rstrip(".") in text
    for step in r["steps"]:
        for c in step.get("src", []):
            assert c and cites.describe(conn, c), (p["id"], step["say"][:40])     # every cited source exists


def test_generic_check_is_unchanged_when_no_pen_is_known(loaded):
    _, tb, _ = loaded
    r = tb.pre_injection_checklist(pen="nonexistent")
    text = say_all(r["steps"])
    assert r["pen"] is None and "dial 2 units" in text and "count slowly to ten" in text and "count the clicks" in text


def test_pen_passages_are_searchable(loaded):
    conn, _, _ = loaded
    hits = evidence.search_evidence(conn, "how long do I hold my Tresiba FlexTouch pen", k=5)
    assert any("Tresiba FlexTouch" in h["title"] for h in hits)
    assert "set_insulin_pen" in TOOL_NAMES


def test_no_drop_reply_follows_the_pen():
    assert "no more than 6 times" in pens.no_drop_say(pens.get("tresiba-flextouch-u100"))
    assert "three tries" in pens.no_drop_say(None)
    obs = vision.parse('{"needle_tip_visible": true, "insulin_at_tip": false, "confident": true}', "drop")
    assert vision.decide("drop", obs, pens.no_drop_say(pens.get("rezvoglar-kwikpen")))["say"].count("4 times") == 1


def test_pen_api_matches_records_saves_choice_and_rebuilds_the_check(tmp_path):
    c = make_client(tmp_path)
    r = c.get("/api/pens").json()
    assert r["chosen"] == "lantus-solostar"                                             # the demo patient's pen
    first = [p for p in r["pens"] if p["matches"]]
    # the demo patient takes insulin glargine and semaglutide: those pens come first
    assert first and all(p["insulin"].startswith(("insulin glargine", "semaglutide")) for p in first) and r["pens"][:len(first)] == first
    assert {p["family"] for p in first} == {"insulin", "glp1"}
    assert c.post("/api/pen", json={"pen": "humalog-kwikpen-u100"}).json()["saved"]
    text = json.dumps(c.get("/api/pen-check").json())
    assert "count slowly to 5 " in text and "Humalog KwikPen" in text and "count the clicks" not in text
    assert c.post("/api/pen", json={"pen": "made-up-pen"}).status_code == 422
    assert c.post("/api/pen", json={"pen": None}).json()["saved"]
    assert c.get("/api/pen-check").json()["pen"] is None


# ---------------- GLP-1 devices ----------------
from prime.glp1_data import DEVICES  # noqa: E402


@pytest.mark.parametrize("d", DEVICES, ids=lambda d: d["id"])
def test_glp1_steps_are_sourced_and_carry_the_right_camera_checks(loaded, d):
    conn, tb, _ = loaded
    r = tb.pre_injection_checklist(pen=d["id"])
    text = say_all(r["steps"])
    checks = [s.get("check") for s in r["steps"] if s.get("check")]
    assert "not insulin" in r["steps"][0]["say"] and r["pen"]["family"] == "glp1"
    if d["device"] == "single-dose autoinjector":
        assert checks == ["cap", "done"] and d["cap_name"] and d["done_visual"]
    else:
        assert checks == ["caps", "drop", "done"] and "counting clicks" in text.lower() or "count clicks" in text.lower()
    assert any(s.get("coach") for s in r["steps"])
    assert ("trained, sighted person" in r["steps"][0]["say"]) == bool(d["low_vision_warning"])
    for step in r["steps"]:
        assert step["src"] and all(cites.describe(conn, c) for c in step["src"]), step["say"][:40]


def test_glp1_camera_checks_use_the_device_wording(tmp_path):
    from tests.fakes import text_msg
    seen = []
    def script():                                        # each request gets a fresh scripted model, so answer by prompt
        def reply(messages):
            prompt = messages[0]["content"][0]["text"]; seen.append(prompt)
            if "remove the gray base cap" in prompt:
                return text_msg('{"pen_visible": true, "cap_on": true, "confident": true}')
            return text_msg('{"window_visible": true, "complete_sign": false, "confident": true}')
        return [reply]
    c = make_client(tmp_path, script=script)
    c.post("/api/pen", json={"pen": "trulicity-pen"})
    img = "data:image/jpeg;base64," + "A" * 200
    r1 = c.post("/api/pen-frames", json={"check": "cap", "frames": [img]}).json()
    r2 = c.post("/api/pen-frames", json={"check": "done", "frames": [img] * 4}).json()
    assert "remove the gray base cap" in seen[0] and "gray plunger is visible" in seen[1]
    assert r1["status"] == "fix" and r1["say"].startswith("The gray base cap still seems to be on")
    assert r2["status"] == "fix" and "care team or pharmacist" in r2["say"]
