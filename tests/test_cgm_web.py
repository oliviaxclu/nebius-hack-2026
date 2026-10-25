import json

from tests.fakes import text_msg
from tests.test_vision import IMG
from tests.test_web import make_client


def client_replying(tmp_path, reply):
    seen = []

    def script():
        def capture(messages):
            seen.append(messages)
            return text_msg(reply)
        return [capture, capture, capture]
    return make_client(tmp_path, script=script), seen


def test_list_choose_and_clear(tmp_path):
    c = make_client(tmp_path)
    r = c.get("/api/cgms").json()
    assert r["chosen"] is None and len(r["cgms"]) == 10 and {x["id"] for x in r["cgms"]} >= {"dexcom-g7", "libre-3", "eversense-365", "other"}
    assert c.post("/api/cgm", json={"cgm": "libre-3"}).json()["readback"] == "Your sensor is now FreeStyle Libre 3 / 3 Plus."
    assert c.get("/api/cgms").json()["chosen"] == "libre-3"
    assert c.post("/api/cgm", json={"cgm": "not-a-sensor"}).status_code == 422
    assert c.post("/api/cgm", json={"cgm": None}).json()["saved"] is True and c.get("/api/cgms").json()["chosen"] is None


def test_check_follows_the_chosen_sensor_and_needs_no_model(tmp_path):
    c = make_client(tmp_path)
    general = c.get("/api/cgm-check").json()                                   # nothing chosen: the general profile, labelled as such
    assert general["cgm"]["id"] == "other" and general["cgm"]["chosen"] is False and general["caveat"]
    c.post("/api/cgm", json={"cgm": "dexcom-g7"})
    g7 = c.get("/api/cgm-check").json()
    text = " ".join(s["say"] for s in g7["steps"])
    assert g7["cgm"]["chosen"] and "Unscrew the cap" in text and "Rub firmly around the sticky patch" in text and g7["caveat"] is None
    assert g7["sources"][0]["url"].startswith("https://") and [s["check"] for s in g7["steps"]] == ["kit", "site", "cap", "applied", "patch"]
    c.post("/api/cgm", json={"cgm": "guardian-4"})
    g4 = c.get("/api/cgm-check").json()
    assert "could not confirm" in g4["caveat"] and not [s for s in g4["steps"] if s["check"] in ("cap", "applied")]
    assert c.get("/api/audit").json()["calls"] == []                            # nothing was sent to a model


def test_site_rotates_after_each_logged_sensor(tmp_path):
    c = make_client(tmp_path)
    c.post("/api/cgm", json={"cgm": "dexcom-g7"})
    seen = []
    for _ in range(3):
        site = c.get("/api/cgm-check").json()["site"]
        assert site and site in " ".join(s["say"] for s in c.get("/api/cgm-check").json()["steps"])
        seen.append(site)
        assert c.post("/api/cgm-done").json()["site"] == site
    assert seen[0] != seen[1] and seen[0] == seen[2]
    c.post("/api/cgm", json={"cgm": "dexcom-g6"})                               # a source that names no site: never invent one
    assert c.get("/api/cgm-check").json()["site"] is None and c.post("/api/cgm-done").json()["site"] is None


def test_frames_endpoint_describes_then_code_speaks(tmp_path):
    c, seen = client_replying(tmp_path, '{"patch_visible": true, "on_skin": true, "edges_lifted": true, "confident": true, "problem": null, "seen": "left edge curled"}')
    c.post("/api/cgm", json={"cgm": "dexcom-g7"})
    before = c.post("/api/chat", json={"message": "I have chest pain"}).json()["remaining"]
    r = c.post("/api/cgm-frames", json={"check": "patch", "frames": [IMG]}).json()
    assert r["status"] == "fix" and "One edge looks lifted" in r["say"] and r["seen"] == "left edge curled" and r["remaining"] == before - 1
    assert "sensor patch" in seen[0][0]["content"][0]["text"]
    call = c.get("/api/audit").json()["calls"][0]
    assert call["purpose"] == "cgm-patch" and "sensor kit, skin or patch" in json.dumps(call) and "hands and pen" not in json.dumps(call)
    assert "not stored" in json.dumps(call) and "base64" not in json.dumps(call)


def test_frames_are_validated(tmp_path):
    c = make_client(tmp_path)
    assert c.post("/api/cgm-frames", json={"check": "patch", "frames": [IMG] * 4}).status_code == 422       # at most three
    assert c.post("/api/cgm-frames", json={"check": "drop", "frames": [IMG]}).status_code == 422             # a pen checkpoint, not a sensor one
    assert c.post("/api/cgm-frames", json={"check": "patch", "frames": ["data:text/html;base64,PGI+"]}).status_code == 422
    assert c.post("/api/cgm-frames", json={"check": "patch", "frames": []}).status_code == 422


def test_a_chatty_or_broken_reply_is_never_ok(tmp_path):
    for reply in ("Looks perfect, go ahead!", "{broken", "```json\n{\"patch_visible\": true}\n```"):
        c, _ = client_replying(tmp_path / str(abs(hash(reply))), reply)
        r = c.post("/api/cgm-frames", json={"check": "patch", "frames": [IMG]}).json()
        assert r["status"] == "unsure" and "go ahead" not in r["say"].lower()


def test_kit_check_uses_the_chosen_sensors_name(tmp_path):
    c, seen = client_replying(tmp_path, '{"kit_visible": true, "brand_text_visible": false, "confident": true, "problem": null, "seen": "box with no readable name"}')
    c.post("/api/cgm", json={"cgm": "libre-2-plus"})
    r = c.post("/api/cgm-frames", json={"check": "kit", "frames": [IMG]}).json()
    assert '"FreeStyle Libre"' in seen[0][0]["content"][0]["text"]
    assert r["status"] == "fix" and "FreeStyle Libre 2 Plus" in r["say"]
