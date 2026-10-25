"""Insulin pen profiles: the spoken pen check follows the person's own pen.

Each profile in pen_data.PENS comes from that pen's official Instructions for Use and carries its source. A field the
source does not give is None, and the step falls back to the generic wording ("follow your pen's instructions" or the
generic cited default) instead of a number nobody checked. Nothing here is a dose: profiles only describe the device.
"""
from __future__ import annotations

from .glp1_data import DEVICES
from .pen_data import PENS

for _p in PENS:
    _p.setdefault("family", "insulin")
for _d in DEVICES:
    _d.setdefault("family", "glp1")
ALL = PENS + DEVICES
BY_ID = {p["id"]: p for p in ALL}
KIND_WORDS = {"rapid-acting": "a rapid-acting (mealtime)", "long-acting": "a long-acting (basal)", "intermediate-acting": "an intermediate-acting",
              "short-acting": "a short-acting", "premixed": "a premixed"}


def get(pen_id: str | None) -> dict | None:
    return BY_ID.get(pen_id or "")


def title(p: dict) -> str:
    return f"{p['name']}: safety test, hold time and mixing" if p.get("family") != "glp1" else f"{p['name']}: how to use it"


def glp1_passage(d: dict) -> dict:
    bits = [f"{d['name']} ({d['maker']}) is a {d['device']} of {d['drug']}, a GLP-1 medicine (not insulin)."]
    bits += [s["say"] for s in d["steps"] if s.get("check") in ("drop", "done")]
    if d["no_click_counting"]:
        bits.append("The instructions say not to set the dose by counting clicks.")
    if d["low_vision_warning"]:
        bits.append("The instructions say people who are blind or have vision problems should not use the pen without help from a trained person.")
    text = ""
    for b in bits:
        if len(text) + len(b) < 880:
            text += (" " if text else "") + b
    return dict(topic="pen-model", title=title(d), source=d["source_title"], year=d["source_year"] or "n.d.",
                evidence_level="manufacturer", text=text, url=d["source_url"])


def passage(p: dict) -> dict:
    """The evidence passage for one pen, written from its verified fields only."""
    if p.get("family") == "glp1":
        return glp1_passage(p)
    bits = [f"{p['name']} ({p['maker']}) is a {'reusable' if p['reusable'] else 'prefilled'} {p['concentration'] or ''} pen of {p['insulin']}."]
    if p["cloudy"] and p["mix"]:
        bits.append(f"It is cloudy and must be mixed before each injection: {p['mix']}.")
    elif p["cloudy"] is None and p["mix"]:
        bits.append(f"For cloudy cartridge insulin: {p['mix']}.")
    elif p["cloudy"] is False:
        bits.append("It is clear and is not mixed.")
    if p["prime_units"]:
        bits.append(f"The safety test (priming) uses {p['prime_units']} units.")
    if p["hold_seconds"]:
        bits.append(f"After pressing the button fully, keep the needle in for {p['hold_seconds']} seconds.")
    if p["prime_retry"]:
        bits.append("If no insulin comes out in the safety test: " + p["prime_retry"].rstrip(".") + ".")
    if p["no_click_counting"]:
        bits.append("The instructions say not to set the dose by counting clicks.")
    if p["low_vision_warning"]:
        bits.append("The instructions say people who are blind or have vision problems should not use the pen without help from a trained person.")
    # Details after the safety facts, only while the passage stays short enough for the model; the spoken steps keep all of them.
    more = []
    if p["dose_increment"] or p["max_dose_units"]:
        more.append(f"It dials in steps of {p['dose_increment'] or 'an unstated number of'} unit{'' if p['dose_increment'] == 1 else 's'}, "
                    f"up to {p['max_dose_units'] or 'an unstated number of'} units per injection.")
    if p["dial_note"]:
        more.append(p["dial_note"].rstrip(".") + ".")
    more += [x.rstrip(".") + "." for x in p["extra_steps"]]
    for m in more:
        if len(" ".join(bits)) + len(m) < 880:
            bits.append(m)
    return dict(topic="pen-model", title=title(p), source=p["source_title"], year=p["source_year"] or "n.d.", evidence_level="manufacturer",
                text=" ".join(b.replace("  ", " ") for b in bits), url=p["source_url"])


def for_insulin(names: list[str]) -> list[str]:
    """Pen ids whose insulin matches one in the person's records, e.g. 'Insulin glargine' -> the glargine pens."""
    wanted = {n.lower().replace("insulin", "").strip() for n in names if n}
    return [p["id"] for p in PENS if any(w and w in (p["insulin"] or "").lower() for w in wanted)] + \
           [d["id"] for d in DEVICES if any(w and w in d["drug"] for w in wanted) or any(w and w in d["name"].lower() for w in wanted)]


def glp1_steps(d: dict, own: str | None) -> list[dict]:
    first = (f"This is {d['name']}, a {d['drug']} pen. It is a GLP-1 medicine, not insulin. Check the label says it is the medicine your care team prescribed." +
             (" Its instructions say that people with vision problems should use it with help from a trained, sighted person." if d["low_vision_warning"] else ""))
    return [{"say": first, "src": [own] if own else []}] + [s | {"src": [own] if own else []} for s in d["steps"]]


def steps(p: dict | None, c, own: str | None) -> list[dict]:
    """The pen check for pen `p` (None = generic). `c(fragment)` resolves a source title to a cite; `own` is this pen's cite."""
    if p and p.get("family") == "glp1":
        return glp1_steps(p, own)
    gen = lambda *t: [c(x) for x in t]                                                 # noqa: E731
    mine = [own] if own else []
    out = [{"say": "Say the name of your insulin and the units you plan to take." +
                   (f" Your pen should be {p['name']}" + (f", {KIND_WORDS[p['kind']]} insulin." if p["kind"] in KIND_WORDS else ".") if p else "") +
                   (" This pen's instructions say that people with vision problems should use it with help from a trained, sighted person."
                    if p and p["low_vision_warning"] else ""),
            "src": mine or gen("Keep the outer cap")}]
    if p:
        out += [{"say": s.rstrip(".") + ".", "src": mine} for s in p["extra_steps"]]
    if p is None:
        out.append({"say": "If your insulin is cloudy, roll the pen gently between your palms about ten times.", "src": gen("Keep the outer cap")})
    elif p["cloudy"] and p["mix"]:
        out.append({"say": f"Your insulin is cloudy. Mix it: {p['mix'].rstrip('.')}. It should look evenly white.", "src": mine})
    elif p["cloudy"] is None and p["mix"]:                                             # reusable pen: depends on the cartridge
        out.append({"say": f"If your cartridge insulin is cloudy, mix it: {p['mix'].rstrip('.')}.", "src": mine})
    out += [
        {"say": "Press a new needle on until it is tight.", "src": gen("Label: prime every time")},
        {"say": "The needle has TWO caps. Take off the big outer cap and keep it. Then take off the small inner cap and throw it away.",
         "src": gen("Two needle caps", "Manufacturer guidance"), "check": "caps"},
    ]
    units = (p or {}).get("prime_units") or (None if p else 2)
    dial = f"dial {units} units" if units else "dial the safety-test amount in your pen's instructions"
    out.append({"say": f"Safety test: {dial}, hold the needle up, tap the pen, press the button all the way. Insulin must come out of the tip. "
                       + (f"{p['prime_retry'].rstrip('.')}. " if p and p["prime_retry"] else "")
                       + "If you cannot see it, ask a helper to look, or tell your care team you need another way to check.",
                "src": (mine if p and (p["prime_units"] or p["prime_retry"]) else []) + gen("Safety test details", "Which pen steps need sight"),
                "check": "drop"})
    if p and p["no_click_counting"]:
        # Several manufacturers say not to set the dose by counting clicks; the generic click-counting step must not override that.
        out.append({"say": "The dose window should be back at zero. Turn the dose selector until your dose lines up with the pointer. "
                           "This pen's instructions say not to set the dose by counting clicks. If you cannot read the dose window, "
                           "ask a trained, sighted helper to check it, or ask your care team about another way." +
                           (f" {p['dial_note'].rstrip('.')}." if p["dial_note"] else ""), "src": mine})
    else:
        out.append({"say": "The dial should be back at zero. Now turn it one click at a time and count the clicks up to your dose." +
                           (f" {p['dial_note'].rstrip('.')}." if p and p["dial_note"] else ""),
                    "src": gen("Two needle caps", "Which pen steps need sight") + (mine if p and p["dial_note"] else [])})
    out.append({"say": "Choose your spot. Use a different spot from last time, at least two inches from your belly button. "
                       "Feel the skin first, and do not use a spot that is lumpy, firm, sore or bruised.",
                "src": gen("Navel distance, scars", "Lumps from injecting"), "coach": True})
    hold = (p or {}).get("hold_seconds")
    out.append({"say": f"Inject, press the button all the way, and count slowly to {hold or 'ten'} before pulling the needle out." +
                       ("" if hold or not p else " Your pen's instructions may give a different time; follow them."),
                "src": (mine if hold else gen("Manufacturer guidance")) + gen("Needle hold time")})
    out += [{"say": "Put the outer cap back on, unscrew the needle, and store the pen without a needle on it.",
             "src": gen("Keep the outer cap", "Manufacturer guidance")},
            {"say": "Tell me when you are done so I can log it."}]
    return out


def hold_seconds(p: dict | None) -> int:
    return (p or {}).get("hold_seconds") or 10


def release(p: dict | None) -> str:
    """What to say when the coach's count ends."""
    return (p or {}).get("release") or "You can take the needle out now."


def no_drop_say(p: dict | None) -> str:
    """What to do when no insulin came out of the tip, in this pen's own words when its IFU gives them."""
    if p and p.get("family") == "glp1":
        return "I didn't see medicine come out. " + (p["flow_retry"].rstrip(".") + "." if p["flow_retry"] else "Check the flow again, as your pen's instructions say.")
    if p and p["prime_retry"]:
        return f"I didn't see insulin come out. Do the safety test again. {p['prime_retry'].rstrip('.')}."
    return "I didn't see insulin come out. Do the safety test again. If none comes out after three tries, change the needle."
