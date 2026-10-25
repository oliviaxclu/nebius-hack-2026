"""GLP-1 (and GIP/GLP-1) injection devices, from each device's official US Instructions for Use. Used by pens.py.

These are not insulin. Every step below paraphrases the IFU named with it; nothing about which dose to take. A step can
carry a camera check (caps, drop, cap, done) or the injection coach. Fields an IFU does not give are None.
Re-check against the current IFU before relying on this beyond a demo.
"""

COACH = "coach"


def S(say, check=None, coach=False):
    return {"say": say, **({"check": check} if check else {}), **({"coach": True} if coach else {})}


SITE_SINGLE = S("Choose your spot on your stomach or thigh, at least two inches from your belly button. Use a different spot each week, "
                "and do not use skin that is lumpy, firm, sore or bruised.", coach=True)
SITE_MULTI = SITE_SINGLE

_LILLY_AUTO = [
    S("Take the pen out of the refrigerator. Leave the gray base cap on until you are ready to inject."),
    S("Check the label: the right medicine and dose, not expired. Check that the pen is not damaged and the medicine is "
      "colorless to slightly yellow, not cloudy, not frozen, with no particles."),
    S("Wash your hands."),
    SITE_SINGLE,
    S("Make sure the pen is locked. Do not unlock it until the clear base is on your skin."),
    S("Pull the gray base cap straight off and throw it away. Do not put it back on, and do not touch the needle.", check="cap"),
    S("Place the clear base flat against your skin, then unlock by turning the lock ring."),
]

_LILLY_KWIKPEN = [
    S("Wash your hands. Pull the pen cap straight off."),
    S("Check the label: the right medicine and strength, not expired. The medicine should be colorless to slightly yellow, "
      "not cloudy, not frozen, with no particles."),
    S("Wipe the red inner seal with an alcohol swab. Push a new pen needle straight on and twist until tight."),
    S("Pull off the outer needle shield and keep it. Pull off the inner needle shield and throw it away.", check="caps"),
    S("Prime: slowly turn the dose knob until you hear 2 clicks and the prime mark is in the dose window. Hold the pen needle up "
      "and tap it so air bubbles rise. Push the dose knob in until it stops and slowly count to 5. A drop should come out of the "
      "needle tip.", check="drop"),
    SITE_MULTI,
    S("Turn the dose knob all the way until it stops and the dose symbol is in the dose window. Do not count clicks."),
    S("Insert the needle. Push the dose knob in until it stops, then slowly count to 5 while holding it."),
    S("Make sure 0 shows in the dose window before you remove the needle. If it does not, put the needle back in and finish. "
      "Do not dial again.", check="done"),
    S("Pull the needle out. Carefully put the outer shield back on, unscrew the needle into a sharps container, and put the pen cap back on."),
]
_LILLY_KWIKPEN_RETRY = ("If no medicine comes out, prime up to 2 more times, then change the needle and prime 1 more time. "
                        "If there is still nothing, contact Lilly")

_NOVO_MULTI = lambda name, flow_retry, extra_check="": [                                       # noqa: E731
    S(f"Wash your hands. Check the name and colored label to make sure it is {name}. Pull off the pen cap."),
    S("Look through the pen window: the medicine should be clear and colorless."),
    S("Push a new needle straight on and turn until it is tight."),
    S("Pull off the outer needle cap and keep it. Pull off the inner needle cap and throw it away. Both caps must be off.", check="caps"),
    S("New pen only: turn the dose selector to the flow check symbol. Hold the pen needle up and press and hold the dose button "
      "until the counter shows 0. A drop should appear at the needle tip. " + flow_retry + ".", check="drop"),
    S("Turn the dose selector until the dose counter shows your dose, lined up with the pointer. Do not set the dose by counting clicks."),
    SITE_MULTI,
    S("Insert the needle as your care team showed you. Keep your fingers off the dose counter."),
    S("Press and hold the dose button until the counter shows 0, then keep pressing and count slowly to 6. "
      "If 0 does not show, the needle may be blocked and no medicine was given: ask your care team or pharmacist what to do.", check="done"),
    S("Remove the needle from your skin, then release the button. Remove the needle into a sharps container and put the pen cap back on."),
]

DEVICES = [
    dict(id="ozempic-pen", name="Ozempic pen", maker="Novo Nordisk", drug="semaglutide", device="multi-dose pen with pen needles",
         steps=_NOVO_MULTI("Ozempic", "If not, repeat up to 6 times, then change the needle and repeat 1 more time. If there is still no drop, do not use the pen"),
         hold_seconds=6, release="You can remove the needle, then release the button.", done_visual="the dose counter shows 0 lined up with the pointer",
         cap_name=None, no_click_counting=True, low_vision_warning=True,
         flow_retry="If no drop appears, repeat the flow check up to 6 times, then change the needle and repeat 1 more time. If there is still no drop, do not use the pen",
         source_url="https://www.novo-pi.com/ozempic.pdf", source_title="Ozempic pen Instructions for Use (Ozempic prescribing information)", source_year="2026"),
    dict(id="wegovy-flextouch-pen", name="Wegovy FlexTouch pen (2.4 mg, 4 doses)", maker="Novo Nordisk", drug="semaglutide", device="multi-dose pen with pen needles",
         steps=_NOVO_MULTI("Wegovy", "If not, check the flow once more (only twice in all), then change the needle and check 1 more time. If there is still no drop, do not use the pen"),
         hold_seconds=6, release="You can remove the needle, then release the button.", done_visual="the dose counter shows 0 lined up with the pointer",
         cap_name=None, no_click_counting=True, low_vision_warning=True,
         flow_retry="If no drop appears, check the flow once more (only twice in all), then change the needle and check 1 more time. If there is still no drop, do not use the pen",
         source_url="https://www.novo-pi.com/wegovy.pdf", source_title="Wegovy FlexTouch pen Instructions for Use (Wegovy prescribing information)", source_year="2026"),
    dict(id="saxenda-pen", name="Saxenda pen", maker="Novo Nordisk", drug="liraglutide", device="multi-dose pen with pen needles",
         steps=_NOVO_MULTI("Saxenda", "If not, repeat up to 6 times, then change the needle and repeat 1 more time. If there is still no drop, do not use the pen"),
         hold_seconds=6, release="You can remove the needle.", done_visual="the dose counter shows 0 lined up with the pointer",
         cap_name=None, no_click_counting=True, low_vision_warning=True,
         flow_retry="If no drop appears, repeat the flow check up to 6 times, then change the needle and repeat 1 more time. If there is still no drop, do not use the pen",
         source_url="https://www.novo-pi.com/saxenda.pdf", source_title="Saxenda pen Instructions for Use (Saxenda prescribing information)", source_year="2026"),
    dict(id="victoza-pen", name="Victoza pen", maker="Novo Nordisk", drug="liraglutide", device="multi-dose pen with pen needles",
         steps=[S("Wash your hands. Check the label to make sure it is your Victoza pen. Pull off the pen cap."),
                S("Check that the medicine in the cartridge is clear, colorless and free of particles. Wipe the rubber stopper with an alcohol swab."),
                S("Screw a new needle on until it is secure."),
                S("Pull off the outer needle cap and keep it. Pull off the inner needle cap and throw it away.", check="caps"),
                S("New pen only: turn the dose selector to the flow check symbol. Hold the pen needle up, tap the cartridge, and press the dose "
                  "button until 0 mg lines up with the pointer. A drop should appear at the needle tip. Repeat up to 6 times; if there is still "
                  "no drop, use a new pen and call Novo Nordisk.", check="drop"),
                S("Turn the dose selector until your dose lines up with the pointer. Do not set the dose by counting clicks."),
                SITE_MULTI,
                S("Insert the needle as your care team showed you. Press the center of the dose button until 0 mg lines up with the pointer.", check="done"),
                S("Keep the button pressed and the needle in for a full count of 6, then withdraw the needle, keeping your thumb on the button."),
                S("Put the outer needle cap back over the needle, unscrew it into a sharps container, and put the pen cap back on.")],
         hold_seconds=6, release="You can withdraw the needle, keeping your thumb on the button until it is out.", done_visual="0 mg lines up with the pointer",
         cap_name=None, no_click_counting=True, low_vision_warning=False,
         flow_retry="If no drop appears, repeat the flow check up to 6 times. If there is still no drop, use a new pen and call Novo Nordisk",
         source_url="https://www.novo-pi.com/victoza.pdf", source_title="Victoza pen Instructions for Use (Victoza prescribing information)", source_year="2025"),
    *[dict(id=i, name=n, maker="Novo Nordisk", drug="semaglutide", device="single-dose autoinjector",
           steps=[S("Wash your hands. Check the pen: do not use it if it looks used or broken, if the medicine in the window is not clear and "
                    "colorless, or if it has expired."),
                  SITE_SINGLE,
                  S("When you are ready to inject, pull the pen cap straight off.", check="cap"),
                  S("Push the pen firmly against your skin. The injection starts when the needle cover is pressed in. You will hear 2 clicks."),
                  S("Keep pressing until the yellow bar in the window has stopped moving. It takes about 5 to 10 seconds.", check="done"),
                  S("When the yellow bar has stopped, lift the pen slowly. Put it in a sharps container right away.")],
           hold_seconds=None, release="If the yellow bar has stopped moving, lift the pen slowly. If it is still moving, keep pressing.",
           done_visual="the yellow bar in the pen window has stopped moving and fills the window", cap_name="the pen cap",
           no_click_counting=None, low_vision_warning=True, flow_retry=None,
           source_url="https://www.novo-pi.com/wegovy.pdf", source_title=t, source_year=y)
      for i, n, t, y in [("wegovy-pen", "Wegovy single-dose pen", "Wegovy single-dose pen Instructions for Use (Wegovy prescribing information)", "2025"),
                         ("wegovy-hd-pen", "Wegovy HD single-dose pen (7.2 mg)", "Wegovy HD pen Instructions for Use (Wegovy prescribing information)", "2026")]],
    dict(id="trulicity-pen", name="Trulicity single-dose pen", maker="Lilly", drug="dulaglutide", device="single-dose autoinjector",
         steps=[*_LILLY_AUTO,
                S("Press and hold the green injection button. You will hear a loud click. Keep holding the clear base firmly against your skin "
                  "until you hear a second loud click, in about 5 to 10 seconds. A soft click just before it is normal."),
                S("Remove the pen from your skin. Check that the gray plunger is visible.", check="done"),
                S("Put the used pen in a sharps container right away.")],
         hold_seconds=10, release="If you heard the second loud click, you can remove the pen. If not, keep holding.",
         done_visual="the gray plunger is visible in the pen window", cap_name="the gray base cap", no_click_counting=None, low_vision_warning=True, flow_retry=None,
         source_url="https://uspl.lilly.com/trulicity/trulicity.html", source_title="Trulicity single-dose pen Instructions for Use (Trulicity US label)", source_year="2023"),
    *[dict(id=i, name=n, maker="Lilly", drug="tirzepatide", device="single-dose autoinjector",
           steps=[*_LILLY_AUTO,
                  S("Press and hold the purple injection button for up to 10 seconds. The first click means the injection started; the second "
                    "click means it is complete. Do not remove the pen before the second loud click."),
                  S("Check that the gray plunger is visible.", check="done"),
                  S("Put the used pen in a sharps container.")],
           hold_seconds=10, release="If you heard the second loud click, you can remove the pen. If not, keep holding.",
           done_visual="the gray plunger is visible in the pen window", cap_name="the gray base cap", no_click_counting=None, low_vision_warning=True, flow_retry=None,
           source_url=u, source_title=t, source_year="2026")
      for i, n, u, t in [("mounjaro-pen", "Mounjaro single-dose pen", "https://uspl.lilly.com/mounjaro/mounjaro.html", "Mounjaro single-dose pen Instructions for Use (Mounjaro US label)"),
                         ("zepbound-pen", "Zepbound single-dose pen", "https://uspl.lilly.com/zepbound/zepbound.html", "Zepbound single-dose pen Instructions for Use (Zepbound US label)")]],
    *[dict(id=i, name=n, maker="Lilly", drug="tirzepatide", device="multi-dose pen with pen needles",
           steps=list(_LILLY_KWIKPEN), hold_seconds=5, release="Check that 0 shows in the dose window before you remove the needle.",
           done_visual="the 0 symbol is in the dose window", cap_name=None, no_click_counting=True, low_vision_warning=True, flow_retry=_LILLY_KWIKPEN_RETRY,
           source_url=u, source_title=t, source_year="2026")
      for i, n, u, t in [("mounjaro-kwikpen", "Mounjaro KwikPen (4 doses)", "https://uspl.lilly.com/mounjaro/mounjaro.html", "Mounjaro KwikPen Instructions for Use (Mounjaro US label)"),
                         ("zepbound-kwikpen", "Zepbound KwikPen (4 doses)", "https://uspl.lilly.com/zepbound/zepbound.html", "Zepbound KwikPen Instructions for Use (Zepbound US label)")]],
]

FIELDS = ("id", "name", "maker", "drug", "device", "steps", "hold_seconds", "release", "done_visual", "cap_name", "no_click_counting",
          "low_vision_warning", "flow_retry", "source_url", "source_title", "source_year")
for _d in DEVICES:
    assert set(_d) == set(FIELDS), (_d["id"], set(FIELDS) ^ set(_d))
