"""The auto-capture decision (prime/static/autocapture.js) runs in the browser. Its step() is pure, so we drive it here with node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_web import make_client

JS = Path(__file__).parent.parent / "prime" / "static" / "autocapture.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")

GOOD = {"mean": 90, "std": 60, "sharp": 1500}          # a clear, well-lit, sharp view (real photos measured 1.8k to 6.5k)


def run(scenario: str):
    """scenario: JS that returns a value; AC (the module) and `go(state, ms, m)` are in scope."""
    code = f"""
const AC = require({json.dumps(str(JS))}); const C = AC.CFG;
const go = (st, t, m) => AC.step(st, Object.assign({{}}, m), t);
const out = (() => {{ {scenario} }})();
console.log(JSON.stringify(out));
"""
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_moving_an_item_into_view_then_holding_still_captures_quickly():
    out = run(f"""
const st = AC.newState(0, false), good = {json.dumps(GOOD)}, acts = [];
let t = 0;
for (let i = 0; i < 4; i++) acts.push(go(st, t += 150, {{...good, diff: 20}}).action);        // the hand moves it in
for (let i = 0; i < 12; i++) acts.push(go(st, t += 150, {{...good, diff: 1.2}}).action);      // then holds still
return {{acts, at: t}};""")
    assert out["acts"][:4] == ["wait"] * 4 and out["acts"].count("capture") >= 1
    first = out["acts"].index("capture")
    assert first == 4 + 7, "captures on the 8th steady sample (about 1.2 s), not before"
    assert out["at"] < C_MIN_WAIT


C_MIN_WAIT = 5000


def test_it_does_not_fire_on_the_first_steady_frames_of_an_empty_view():
    out = run(f"""
const st = AC.newState(0, false), good = {json.dumps(GOOD)};
const acts = []; let t = 0;
for (let i = 0; i < 30; i++) acts.push(go(st, t += 100, {{...good, diff: 1}}).action);       // 3 s of a still view, nobody moved anything
return acts;""")
    assert "capture" not in out


def test_a_still_view_is_captured_after_the_wait_for_someone_already_holding_it():
    out = run(f"""
const st = AC.newState(0, false), good = {json.dumps(GOOD)};
let a = []; for (let t = 150; t <= 6000; t += 150) a.push([t, go(st, t, {{...good, diff: 1}}).action]);
return a.find(x => x[1] === "capture");""")
    assert out and out[0] >= 5000


def test_after_a_bad_result_it_never_resends_the_same_view():
    out = run(f"""
const st = AC.newState(0, true), good = {json.dumps(GOOD)}; let hits = 0;
for (let t = 150; t <= 30000; t += 150) if (go(st, t, {{...good, diff: 1}}).action === "capture") hits++;     // 30 s of the unchanged view
const moved = AC.newState(0, true); let a = [];
for (let i = 0; i < 3; i++) a.push(go(moved, 150 * (i + 1), {{...good, diff: 25}}).action);                 // the person adjusts
for (let i = 0; i < 10; i++) a.push(go(moved, 150 * (i + 4), {{...good, diff: 1}}).action);
return {{hits, after: a.includes("capture")}};""")
    assert out == {"hits": 0, "after": True}


def test_too_dark_glare_and_a_covered_lens_give_spoken_hints_and_never_capture():
    out = run("""
const res = {};
for (const [name, m] of Object.entries({ dark: {mean: 20, std: 20, sharp: 90}, glare: {mean: 240, std: 30, sharp: 900}, covered: {mean: 60, std: 2, sharp: 0} })) {
  const st = AC.newState(0, false); st.sawMotion = true; let cap = false, say = "";
  for (let i = 0; i < 20; i++) { const r = go(st, 150 * (i + 1), {...m, diff: 1}); if (r.action === "capture") cap = true; if (r.say) say = r.say; }
  res[name] = {cap, say};
}
return res;""")
    assert not any(v["cap"] for v in out.values())
    assert "dark" in out["dark"]["say"] and "glare" in out["glare"]["say"] and "can't see anything" in out["covered"]["say"]


def test_a_blurry_but_still_picture_is_not_sent_and_asks_for_a_steadier_hold():
    out = run("""
const st = AC.newState(0, false); st.sawMotion = true; let cap = false, say = "";
for (let i = 0; i < 12; i++) { const r = go(st, 150 * (i + 1), {mean: 90, std: 60, sharp: 60, diff: 1}); if (r.action === "capture") cap = true; if (r.say) say = r.say; }
return {cap, say};""")
    assert out["cap"] is False and "blurry" in out["say"]


def test_noise_in_a_dim_webcam_does_not_count_as_movement_but_a_real_shift_does():
    out = run(f"""
const good = {json.dumps(GOOD)}, quiet = AC.newState(0, false); quiet.sawMotion = true;
const noisy = [...Array(10)].map((_, i) => go(quiet, 150 * (i + 1), {{...good, diff: 3.5}}).action);       // measured noise of 3.5 is still steady
const shake = AC.newState(0, false); shake.sawMotion = true;
const shifted = [...Array(10)].map((_, i) => go(shake, 150 * (i + 1), {{...good, diff: 10.4}}).action);       // a 6 px shift is movement
return {{noisy: noisy.includes("capture"), shifted: shifted.includes("capture")}};""")
    assert out == {"noisy": True, "shifted": False}


def test_the_script_is_served_by_the_app_and_the_page_loads_it(tmp_path):
    c = make_client(tmp_path)
    r = c.get("/autocapture.js")
    assert r.status_code == 200 and "javascript" in r.headers["content-type"] and "AutoCapture" in r.text
    assert '<script src="/autocapture.js"></script>' in c.get("/").text
