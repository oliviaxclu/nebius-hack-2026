"""Sensor-application camera checkpoints: the model DESCRIBES one frame; code decides what Prime says.

Same rule as vision.py: every sentence the user hears is a fixed template below, so a model mistake can make Prime less
helpful but never makes it give dose or glucose advice. A reading is always a second check, never a go-ahead.

  kit          is a CGM sensor kit in view, and does it show the picked sensor's name?
  site         is bare skin in view, with nothing over it and no sensor already on it?
  cap          is the applicator's cap off?
  labels       are the paper labels off the sticky side? (Dexcom G6)
  applied      is the applicator held flat against the skin?
  patch        is the finished patch stuck flat, no lifted edges?
  transmitter  is the transmitter snapped into the holder on the skin? (Dexcom G6)
"""
from __future__ import annotations

import json
import re

from .cgm_data import CHECKS
from .vision import _COMMON, HELPER, SECOND

# vision.TIPS talk about pens and needles, so sensor checks get their own wording (same problem codes).
TIPS = {"blur": "The picture was blurry. Hold it still and try again.",
        "glare": "There was glare. Tilt it slightly away from the light and try again.",
        "dark": "It was too dark. Turn on a light and try again.",
        "cut_off": "Part of it was out of view. Move it a little farther from the camera and try again.",
        "covered": "Something was covering it. Move your fingers or clothing away and try again."}

_SEEN = '"seen": "what you actually see, max 12 words"'
_TAIL = '"confident": true or false,\n "problem": "blur" | "glare" | "dark" | "cut_off" | "covered" | null,\n ' + _SEEN + "}"

PROMPTS = {
    "kit": """This is a photo of a person holding a continuous glucose monitor (CGM) sensor kit, applicator or its packaging.
""" + _COMMON + """
{"kit_visible": true or false,             // is a CGM sensor kit, applicator or packaging in view
 "brand_text_visible": true, false or null, // can you read the name "{keyword}" on it (null if you cannot tell)
 """ + _TAIL,
    "site": """This is a photo of a person showing the area of skin where a CGM sensor will go.
""" + _COMMON + """
{"skin_visible": true or false,           // is a bare patch of skin in view
 "covered": true, false or null,          // is clothing, a bandage, cream or thick hair covering the spot
 "sensor_on_skin": true, false or null,   // is a sensor or patch already stuck on that spot
 """ + _TAIL,
    "cap": """This is a photo of a person holding a CGM sensor applicator.
""" + _COMMON + """
A cap is a separate removable cover, often a different colour, that sits over the open end where the sensor comes out.
{"applicator_visible": true or false,     // is the applicator in view
 "open_end_visible": true or false,       // can you SEE the open end itself, with nothing covering it (false if a cap or anything else covers it, or the end is out of view)
 "cap_on": true, false or null,           // is a cap still covering that open end
 """ + _TAIL,
    "labels": """This is a photo of the sticky underside of a CGM sensor applicator.
""" + _COMMON + """
{"adhesive_visible": true or false,       // is the sticky side in view
 "label_on": true, false or null,         // is a paper label still covering any of it
 """ + _TAIL,
    "applied": """This is a photo of a person pressing a CGM sensor applicator against their skin.
""" + _COMMON + """
{"applicator_visible": true or false,     // is the applicator in view
 "flat_on_skin": true, false or null,     // is its whole base flat against the skin
 """ + _TAIL,
    "patch": """This is a photo of a CGM sensor patch that was just stuck onto skin.
""" + _COMMON + """
{"patch_visible": true or false,          // is a sensor patch in view
 "on_skin": true, false or null,          // is it stuck on a person's skin (not lying on a table or held in the air)
 "edges_lifted": true, false or null,     // is any edge lifted, curled or peeling
 """ + _TAIL,
    "transmitter": """This is a photo of a CGM sensor on skin with a transmitter being attached.
""" + _COMMON + """
{"holder_visible": true or false,         // is the sensor holder on the skin in view
 "transmitter_snapped": true, false or null, // does the transmitter sit fully in the holder
 """ + _TAIL,
}
assert set(PROMPTS) == set(CHECKS)

_FIELDS = {"kit": ("kit_visible", "brand_text_visible"), "site": ("skin_visible", "covered", "sensor_on_skin"),
           "cap": ("applicator_visible", "open_end_visible", "cap_on"), "labels": ("adhesive_visible", "label_on"),
           "applied": ("applicator_visible", "flat_on_skin"), "patch": ("patch_visible", "on_skin", "edges_lifted"),
           "transmitter": ("holder_visible", "transmitter_snapped")}
_SEEN_FIELDS = {"open_end_visible", "kit_visible", "skin_visible", "applicator_visible", "adhesive_visible", "patch_visible", "holder_visible"}


def prompt(check: str, keyword: str = "") -> str:
    """The prompt for one checkpoint. Only `kit` uses the sensor's name."""
    return PROMPTS[check].replace("{keyword}", keyword or "CGM")


def parse(raw: str | None, check: str) -> dict:
    """The JSON observation from the model's reply. Anything malformed reads as 'could not see'."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    try:
        obs = json.loads(re.sub(r"//[^\n]*", "", m.group(0))) if m else {}
    except (json.JSONDecodeError, TypeError):
        obs = {}
    obs = obs if isinstance(obs, dict) else {}
    out = {"confident": obs.get("confident") is True, "problem": obs.get("problem") if obs.get("problem") in TIPS else None,
           "seen": str(obs.get("seen") or "")[:100]}
    for k in _FIELDS[check]:
        out[k] = (obs.get(k) is True) if k in _SEEN_FIELDS else (obs.get(k) if isinstance(obs.get(k), bool) else None)
    return out


def _unsure(obs: dict, what: str) -> dict:
    return {"status": "unsure", "seen": obs.get("seen", ""),
            "say": " ".join([f"I couldn't see {what} clearly.", TIPS.get(obs.get("problem")) or "Try again with it held still and well lit.", HELPER])}


def decide(check: str, obs: dict, name: str = "your sensor", keyword: str = "") -> dict:
    """status: ok (looks right), fix (something to do), unsure (could not tell). Never 'safe to use'."""
    seen = obs.get("seen", "")
    ok = lambda say: {"status": "ok", "say": f"{say} {SECOND}", "seen": seen}          # noqa: E731
    fix = lambda say: {"status": "fix", "say": say, "seen": seen}                       # noqa: E731
    if not obs.get("confident"):
        return _unsure(obs, {"kit": "the sensor kit", "site": "the skin", "cap": "the applicator", "labels": "the sticky side",
                             "applied": "the applicator on your skin", "patch": "the patch", "transmitter": "the transmitter"}[check])
    if check == "kit":
        if not obs["kit_visible"]:
            return _unsure(obs, "the sensor kit")
        if keyword and obs["brand_text_visible"] is False:
            return fix(f"I can see a sensor kit, but I can't read the name {keyword} on it. Check that it is the {name} you picked, or pick the right sensor.")
        return ok(f"I can see a sensor kit{' that matches ' + name if keyword and obs['brand_text_visible'] else ''}.")
    if check == "site":
        if obs["sensor_on_skin"]:
            return fix("There already seems to be a sensor on this spot. Choose a different spot.")
        if obs["covered"]:
            return fix("Something seems to be covering the skin. Clear it away and show me bare skin.")
        if obs["skin_visible"] and obs["covered"] is False and obs["sensor_on_skin"] is False:
            return ok("I can see bare skin with nothing on it.")
        return _unsure(obs, "the skin")
    if check == "cap":
        if not obs["applicator_visible"]:
            return _unsure(obs, "the applicator")
        if obs["cap_on"]:
            return fix("The cap still seems to be on. Take it off as your steps say, and don't touch inside.")
        if obs["cap_on"] is False and obs["open_end_visible"]:        # "ok" needs the open end actually seen, not just no cap noticed
            return ok("The cap seems to be off and I can see the open end.")
        return _unsure(obs, "the open end of the applicator")
    if check == "labels":
        if not obs["adhesive_visible"] or obs["label_on"] is None:
            return _unsure(obs, "the sticky side")
        return fix("A paper label still seems to cover the sticky side. Peel it off without touching the sticky part.") if obs["label_on"] else ok("The sticky side looks clear.")
    if check == "applied":
        if not obs["applicator_visible"] or obs["flat_on_skin"] is None:
            return _unsure(obs, "the applicator on your skin")
        return ok("The applicator looks flat on your skin.") if obs["flat_on_skin"] else fix("It doesn't look flat. Press the whole base against your skin and show me again.")
    if check == "patch":
        if not obs["patch_visible"] or obs["on_skin"] is not True or obs["edges_lifted"] is None:
            return _unsure(obs, "the patch on your skin")
        return fix("One edge looks lifted. Press around the edges of the patch and show me again.") if obs["edges_lifted"] else ok("The patch looks flat with no lifted edges.")
    if not obs["holder_visible"] or obs["transmitter_snapped"] is None:
        return _unsure(obs, "the transmitter")
    return ok("The transmitter looks snapped in.") if obs["transmitter_snapped"] else fix("The transmitter doesn't look fully in. Press it firmly into the holder and show me again.")
