"""The no-dose-advice filter: real dose advice is always removed; Prime's own device and site guidance never is."""
import re

import pytest

from prime import pens, sites, vision
from prime.agent import enforce_no_dose_advice, is_dose_advice
from prime.pen_data import PENS

DOSE_ADVICE = [
    "Take 30 units tonight.", "You should increase your insulin dose.", "Skip your insulin tomorrow.",
    "Try to double your dose of insulin.", "Reduce your night dose by 4 units.", "You should take 4 more units tonight.",
    "Inject 4 extra units with dinner.", "Increase your basal dose by 2 units.", "You could raise your Lantus to 24 units.",
    "Try lowering your insulin by 10 percent.", "Hold off on your bedtime insulin.", "Double your dose tomorrow.",
    "Don't take your insulin tonight.", "I'd go up to 2.4 mg next week.", "Switch to 1 mg of Ozempic.",
    "Consider cutting back your Tresiba by 2 units.", "Your dose should be 22 units.", "Your dose should go up.",
    "After the safety test, inject 20 units.", "Skip this week's Mounjaro shot.", "Take an extra shot of Humalog with lunch.",
    "Then reduce your mealtime insulin.", "Use 2 units less at breakfast.",
]

MODEL_LIKE_SAFE = [
    "Do not change or add insulin on your own.", "Ask your care team whether to change your insulin dose.",
    "Your insulin log shows 18 units each night.", "Contact your pharmacist about the pen.",
    "The insulin dose was raised on September 28.", "Insulin glargine works over about a day.",
    "For today's injection, use the upper-left part of your belly.", "Today, inject into the upper left of your belly.",
    "Using the same spot can cause lumps that change how insulin is absorbed.",
    "Using the same spot again and again can change how your insulin is absorbed.",
    "You've injected in the lower-right part of your belly for 5 of your last 7 shots.",
    "Feel that area for firm or lumpy skin, and if you find any, avoid it and tell your care team.",
    "Logged 20 units of insulin glargine at 9:30 PM.", "Mornings ran about 70 above your usual even with 20 units logged.",
    "Hold the pen with the needle pointing up and tap it.", "Count slowly to 6 before you pull the needle out.",
    "Insulin may not have been fully delivered, for example if the pen did not release the dose.",
    "Steroids can raise glucose for several hours.", "Before you inject, feel the skin.",
    "I can't advise on medicine doses. Please ask your care team or pharmacist.",
]


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def prime_own_texts():
    """Every sentence Prime itself speaks in the pen check, site plan, coach and camera checks."""
    def c(_):
        return "src:00000000"
    out = []
    for p in [None, *pens.ALL]:
        out += [s["say"] for s in pens.steps(p, c, "src:11111111" if p else None)]
        out.append(pens.no_drop_say(p))
    out += [t for t, _ in sites.CHECKS] + list(sites.ZONES.values())
    out.append("You used the lower right of your belly for 5 of your last 7 injections. Using the same spot can cause lumps that change how "
               "insulin is absorbed. Feel that area for firm or lumpy skin, and if you find any, avoid it and tell your care team.")
    for check, cases in [("caps", [{"needle_visible": v, "outer_cap_on": a, "inner_cap_on": b, "confident": True, "problem": None}
                                   for v in (True, False) for a in (True, False, None) for b in (True, False, None)]),
                         ("drop", [{"needle_tip_visible": True, "insulin_at_tip": a, "confident": True, "problem": None} for a in (True, False, None)])]:
        out += [vision.decide(check, o)["say"] for o in cases]
    for d in pens.DEVICES:
        for o in ({"pen_visible": True, "cap_on": a, "confident": True, "problem": None} for a in (True, False, None)):
            out.append(vision.decide("cap", o, cap_name=d["cap_name"] or "the cap")["say"])
        for o in ({"window_visible": True, "complete_sign": a, "confident": True, "problem": None} for a in (True, False, None)):
            out.append(vision.decide("done", o, done_visual=d["done_visual"])["say"])
        out.append(d["release"])
    return [s for t in out for s in sentences(t)]


@pytest.mark.parametrize("s", DOSE_ADVICE)
def test_dose_advice_is_removed(s):
    out, removed = enforce_no_dose_advice(f"Mornings were high. {s} Ask about it.")
    assert removed and s.rstrip(".") in removed[0] and s not in out, s


@pytest.mark.parametrize("s", MODEL_LIKE_SAFE)
def test_safe_language_is_kept(s):
    assert not is_dose_advice(s), s


def test_none_of_primes_own_guidance_is_removed():
    flagged = [s for s in prime_own_texts() if is_dose_advice(s)]
    assert not flagged, flagged[:5]
