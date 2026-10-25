"""Pen-check camera checkpoints with Nemotron-3.5-Super-VL: the model DESCRIBES a few cropped frames; code decides what Prime says.

Two checkpoints, both steps the pen passages say need sight:
  caps  one frame: are the big outer and small inner needle caps off?
  drop  a few frames while the button is pressed in the safety test: did insulin come out of the tip?
  cap   one frame, single-dose GLP-1 pens: is the cap over the needle end ({cap_name}) off?
  done  a few frames right after injecting: is the pen's own "finished" sign showing ({done_visual}, from its IFU)?
Every sentence the user hears is a fixed template below, taken from the cited pen passages, so a model mistake can make
Prime less helpful but never makes it give dose advice. A reading is always a second check, never a go-ahead.
"""
from __future__ import annotations

import json
import re

CHECKS = ("caps", "drop", "cap", "done")
MAX_FRAMES = 6

_COMMON = """Describe ONLY what is visible. Do not guess: if something is blurry, cut off, covered by a finger or glare, or not
in view, answer null and set "confident" to false. Return only this JSON object, nothing else."""

PROMPTS = {
    "caps": f"""This is a photo of a person with low vision holding an insulin pen with a pen needle attached.
A pen needle has TWO caps: a big outer cap (wide, covers the whole needle hub) and a small thin inner cap over the needle itself.
{_COMMON}
{{"needle_visible": true or false,    // can you see the bare needle itself (false if a cap covers it)
 "outer_cap_on": true, false or null, // is the big outer cap still on
 "inner_cap_on": true, false or null, // is the small inner cap still on (only answerable once the outer cap is off)
 "confident": true or false,
 "problem": "blur" | "glare" | "dark" | "cut_off" | "covered" | null}}""",
    "drop": """These are {n} frames, in order, about half a second apart, of a person doing the safety test (priming) with an insulin pen:
the needle points up and they press the button. Look closely at the very tip of the needle.
""" + _COMMON + """
{"needle_tip_visible": true or false,   // is the needle tip in view and sharp in at least one frame
 "insulin_at_tip": true, false or null, // does a drop or a stream of liquid appear at the tip in any frame
 "confident": true or false,
 "problem": "blur" | "glare" | "dark" | "cut_off" | "covered" | null}""",
}

PROMPTS["cap"] = """This is a photo of a person holding a single-use medicine injection pen (an autoinjector).
Its instructions say to remove {cap_name} just before injecting.
""" + _COMMON + """
{"pen_visible": true or false,          // can you see the pen, including the end where the needle is
 "cap_on": true, false or null,         // is {cap_name} still on that end
 "confident": true or false,
 "problem": "blur" | "glare" | "dark" | "cut_off" | "covered" | null}"""
PROMPTS["done"] = """These are {n} frames, in order, about half a second apart, of a medicine injection pen just after an injection.
The pen's instructions say the injection is complete when {done_visual}. Look at the pen window or dose counter.
""" + _COMMON + """
{"window_visible": true or false,       // can you see the pen window or dose counter clearly in at least one frame
 "complete_sign": true, false or null,  // is the completion sign described above showing in the last frames
 "confident": true or false,
 "problem": "blur" | "glare" | "dark" | "cut_off" | "covered" | null}"""

TIPS = {"blur": "The picture was blurry. Hold the pen still and try again.",
        "glare": "There was glare. Tilt the pen slightly away from the light and try again.",
        "dark": "It was too dark. Turn on a light and try again.",
        "cut_off": "Part of the pen was out of view. Move it a little farther from the camera and try again.",
        "covered": "Your fingers were covering the needle end. Hold the pen lower down and try again."}
SECOND = "This is only a second check."
HELPER = "If you are not sure, ask someone to look."


def parse(raw: str | None, check: str) -> dict:
    """The JSON observation from the model's reply. Anything malformed reads as 'could not see'."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S)
    m = re.search(r"\{.*\}", text, re.S)
    try:
        obs = json.loads(re.sub(r"//[^\n]*", "", m.group(0))) if m else {}
    except (json.JSONDecodeError, TypeError):
        obs = {}
    obs = obs if isinstance(obs, dict) else {}
    tri = lambda k: obs.get(k) if isinstance(obs.get(k), bool) else None          # noqa: E731
    out = {"confident": obs.get("confident") is True, "problem": obs.get("problem") if obs.get("problem") in TIPS else None}
    if check == "caps":
        out |= {"needle_visible": obs.get("needle_visible") is True, "outer_cap_on": tri("outer_cap_on"), "inner_cap_on": tri("inner_cap_on")}
    elif check == "drop":
        out |= {"needle_tip_visible": obs.get("needle_tip_visible") is True, "insulin_at_tip": tri("insulin_at_tip")}
    elif check == "cap":
        out |= {"pen_visible": obs.get("pen_visible") is True, "cap_on": tri("cap_on")}
    else:
        out |= {"window_visible": obs.get("window_visible") is True, "complete_sign": tri("complete_sign")}
    return out


def _unsure(obs: dict, what: str) -> dict:
    say = [f"I couldn't see {what} clearly."]
    say.append(TIPS.get(obs["problem"]) or "Try again with the pen still and well lit.")
    return {"status": "unsure", "say": " ".join(say + [HELPER])}


NOT_DONE = "I couldn't confirm that the injection finished. Do not guess: ask your care team or pharmacist what to do."


def decide(check: str, obs: dict, no_drop: str = "I didn't see insulin come out. Do the safety test again. "
                                                     "If none comes out after three tries, change the needle.",
           cap_name: str = "the cap", done_visual: str = "the pen shows it is finished") -> dict:
    """status: ok (looks right), fix (something to do), unsure (could not tell). Never 'safe to inject'."""
    if check == "caps":
        # A cap on hides the needle, so a cap the model is sure about counts even when the needle is not visible.
        if not obs["confident"]:
            return _unsure(obs, "the needle")
        if obs["outer_cap_on"] is True:
            return {"status": "fix", "say": "The big outer cap still seems to be on. Take it off and keep it for later."}
        if obs["inner_cap_on"] is True:
            return {"status": "fix", "say": "The small inner cap still seems to be on. Take it off and throw it away."}
        if obs["outer_cap_on"] is False and obs["inner_cap_on"] is False and obs["needle_visible"]:
            return {"status": "ok", "say": f"Both needle caps seem to be off. {SECOND} {HELPER}"}
        return _unsure(obs, "the needle" if not obs["needle_visible"] else "both caps")
    if check == "cap":
        if not obs["pen_visible"] or not obs["confident"] or obs["cap_on"] is None:
            return _unsure(obs, "the end of the pen")
        if obs["cap_on"]:
            return {"status": "fix", "say": f"{cap_name[0].upper() + cap_name[1:]} still seems to be on. Pull it straight off when you are ready to inject."}
        return {"status": "ok", "say": f"{cap_name[0].upper() + cap_name[1:]} seems to be off. Do not touch the needle end. {SECOND}"}
    if check == "done":
        if not obs["window_visible"] or not obs["confident"] or obs["complete_sign"] is None:
            return {"status": "unsure", "say": f"I couldn't see the pen window clearly. {TIPS.get(obs['problem'], '')} {NOT_DONE}".replace("  ", " ")}
        if obs["complete_sign"]:
            return {"status": "ok", "say": f"It looks finished: {done_visual}. {SECOND} {HELPER}"}
        return {"status": "fix", "say": f"I didn't see the finished sign ({done_visual}). {NOT_DONE}"}
    if not obs["needle_tip_visible"] or not obs["confident"] or obs["insulin_at_tip"] is None:
        return _unsure(obs, "the needle tip")
    if obs["insulin_at_tip"]:
        return {"status": "ok", "say": f"I think I saw insulin at the needle tip. {SECOND} {HELPER}"}
    return {"status": "fix", "say": no_drop}
