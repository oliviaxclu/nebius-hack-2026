import base64
import json

from prime import db, vision
from prime.agent import enforce_no_dose_advice
from prime.config import Settings
from prime.llm import LLM
from prime.privacy import Redactor
from tests.fakes import ScriptedClient, text_msg
from tests.test_web import make_client

IMG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8 fake jpeg " * 30).decode()


def caps(**kw):
    return vision.parse(json.dumps({"needle_visible": True, "outer_cap_on": False, "inner_cap_on": False, "confident": True, "problem": None} | kw), "caps")


def drop(**kw):
    return vision.parse(json.dumps({"needle_tip_visible": True, "insulin_at_tip": True, "confident": True, "problem": None} | kw), "drop")


def test_parse_tolerates_think_fences_and_comments_and_rejects_junk():
    raw = '<think>looking</think>```json\n{"needle_visible": true, // yes\n "outer_cap_on": false, "inner_cap_on": true, "confident": true, "problem": null}\n```'
    assert vision.parse(raw, "caps") == {"confident": True, "problem": None, "needle_visible": True, "outer_cap_on": False, "inner_cap_on": True}
    for junk in (None, "", "no json", '{"needle_visible": "yes", "outer_cap_on": "no", "problem": "smudge"}', "[1]"):
        o = vision.parse(junk, "caps")
        assert o["needle_visible"] is False and o["outer_cap_on"] is None and o["problem"] is None and o["confident"] is False


def test_caps_outcomes():
    assert vision.decide("caps", caps())["status"] == "ok"
    assert "outer cap still seems to be on" in vision.decide("caps", caps(outer_cap_on=True, inner_cap_on=None))["say"]
    # seen with the real model: the cap hides the needle, so needle_visible is false, but the cap is still the answer
    assert vision.decide("caps", caps(needle_visible=False, outer_cap_on=True, inner_cap_on=None))["status"] == "fix"
    assert vision.decide("caps", caps(needle_visible=False))["status"] == "unsure"                 # "both off" needs the needle seen
    assert "inner cap still seems to be on" in vision.decide("caps", caps(inner_cap_on=True))["say"]
    assert vision.decide("caps", caps(inner_cap_on=None))["status"] == "unsure"            # can't tell the inner cap: never "ok"
    r = vision.decide("caps", caps(confident=False, problem="covered"))
    assert r["status"] == "unsure" and "fingers were covering" in r["say"]


def test_drop_outcomes():
    ok = vision.decide("drop", drop())
    assert ok["status"] == "ok" and vision.SECOND in ok["say"]
    none = vision.decide("drop", drop(insulin_at_tip=False))
    assert none["status"] == "fix" and "three tries, change the needle" in none["say"]
    for o in (drop(insulin_at_tip=None), drop(needle_tip_visible=False), drop(confident=False, problem="glare")):
        assert vision.decide("drop", o)["status"] == "unsure"


def test_no_reply_ever_reads_as_dose_advice_or_a_go_ahead():
    replies = [vision.decide("caps", caps(outer_cap_on=a, inner_cap_on=b, confident=c, problem=p))
               for a in (True, False, None) for b in (True, False, None) for c in (True, False) for p in (None, "blur")]
    replies += [vision.decide("drop", drop(insulin_at_tip=a, needle_tip_visible=v, confident=c))
                for a in (True, False, None) for v in (True, False) for c in (True, False)]
    for r in replies:
        assert enforce_no_dose_advice(r["say"])[1] == [], r["say"]
        assert not any(w in r["say"].lower() for w in ("safe to inject", "you can inject", "go ahead", "units"))


def test_llm_vision_sends_images_unredacted_and_never_stores_them(tmp_path):
    conn = db.connect(tmp_path / "v.db")
    image = "data:image/jpeg;base64," + base64.b64encode(b"Hale" * 60).decode() + "Hale"     # base64 that contains a "name"
    client = ScriptedClient([text_msg('{"needle_visible": false}')])
    s = Settings(home=tmp_path, api_key="k", base_url="http://x", model="m", vision_model="vl")
    LLM(s, conn, Redactor({"name": ["Ray Hale"]}), client=client).vision("Patient Ray Hale. " + vision.PROMPTS["caps"], [image, image])
    content = client.requests[0]["messages"][0]["content"]
    assert client.requests[0]["model"] == "vl" and [p["image_url"]["url"] for p in content[1:]] == [image, image]
    assert "Hale" not in content[0]["text"] and "max_tokens" not in client.requests[0]
    row = conn.execute("SELECT sent, model FROM llm_audit").fetchone()
    assert row["model"] == "vl" and "base64" not in row["sent"] and "2 cropped frames" in row["sent"]


def test_pen_frames_endpoint(tmp_path):
    reply = '{"needle_tip_visible": true, "insulin_at_tip": false, "confident": true, "problem": null}'
    seen = []
    def script():
        def capture(messages):
            seen.append(messages)
            return text_msg(reply)
        return [capture]
    c = make_client(tmp_path, script=script)
    before = c.post("/api/chat", json={"message": "I have chest pain"}).json()["remaining"]
    r = c.post("/api/pen-frames", json={"check": "drop", "frames": [IMG] * 6}).json()
    assert r["status"] == "fix" and "Do the safety test again" in r["say"] and r["remaining"] == before - 1
    assert "6 frames, in order" in seen[0][0]["content"][0]["text"]
    assert c.post("/api/pen-frames", json={"check": "drop", "frames": [IMG] * 7}).status_code == 422
    assert c.post("/api/pen-frames", json={"check": "dial", "frames": [IMG]}).status_code == 422
    assert c.post("/api/pen-frames", json={"check": "caps", "frames": ["data:text/html;base64,PGI+"]}).status_code == 422
    call = c.get("/api/audit").json()["calls"][0]
    assert call["purpose"] == "pen-drop" and "not stored" in json.dumps(call) and "base64" not in json.dumps(call)
    steps = c.get("/api/pen-check").json()["steps"]
    assert [s.get("check") for s in steps if s.get("check")] == ["caps", "drop"]
