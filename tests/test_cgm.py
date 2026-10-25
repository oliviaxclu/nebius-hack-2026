import json

import pytest

from prime import cgm, cgm_vision
from prime.cgm_data import CGMS, CHECKS

IDS = [c["id"] for c in CGMS]


def test_catalog_covers_the_major_families_and_a_fallback():
    for want in ("dexcom-g6", "dexcom-g7", "dexcom-stelo", "libre-2-plus", "libre-3", "lingo",
                 "simplera-sync", "guardian-4", "eversense-365", "other"):
        assert want in IDS
    assert len(IDS) == len(set(IDS))


@pytest.mark.parametrize("c", CGMS, ids=IDS)
def test_every_profile_is_sourced_and_well_formed(c):
    steps = cgm.steps(c)
    assert steps[0]["check"] == "kit" and steps[-1]["check"] == "patch" and any(s["check"] == "site" for s in steps)
    for s in steps:
        assert s["check"] in CHECKS and "{site}" not in s["say"] and s["say"].strip()
        for bad in (" units", "mg/dL", "mmol", "dose "):                 # profiles describe a device, never a dose or a reading
            assert bad not in s["say"], (c["id"], s["say"][:50])
    assert c["after"]
    if c["coverage"] == "limited":
        assert c["caveat"]
    else:
        assert c["sources"], "a full flow needs a published source"
    for title, url in c["sources"]:
        assert title and url.startswith("https://")


def test_limited_sensors_never_claim_insertion_steps():
    for cid in ("guardian-4", "eversense-365", "other"):
        c = cgm.get(cid)
        assert c["coverage"] == "limited"
        assert not any(s["check"] in ("applied", "cap", "labels", "transmitter") for s in c["steps"] if cid != "eversense-365"), cid
    assert cgm.get("eversense-365")["caveat"].startswith("The Eversense sensor is placed under your skin by a healthcare provider")


def test_site_rotation_and_generic_fallback():
    g7 = cgm.get("dexcom-g7")
    first = cgm.next_site(g7, None)
    assert first in g7["sites"] and cgm.next_site(g7, first) != first and cgm.next_site(g7, "somewhere unknown") == g7["sites"][0]
    assert f"use the {first}" in " ".join(s["say"] for s in cgm.steps(g7, None))
    g6 = cgm.get("dexcom-g6")                                             # no site named by the source: never invent one
    assert cgm.next_site(g6, None) is None and cgm.GENERIC_SITE in " ".join(s["say"] for s in cgm.steps(g6, None))


def test_listing_and_lookup():
    assert [x["id"] for x in cgm.listing()] == IDS and cgm.get("nope") is None and cgm.get(None) is None


def test_passage_is_written_from_the_profile():
    p = cgm.passage(cgm.get("libre-3"))
    assert p["topic"] == "cgm-model" and p["evidence_level"] == "manufacturer" and p["url"].startswith("https://") and len(p["text"]) <= 880


# ---- cgm_vision: the model describes, code decides ----

def reply(**kw):
    return json.dumps({"confident": True, "problem": None, "seen": "test", **kw})


def decide(check, **kw):
    return cgm_vision.decide(check, cgm_vision.parse(reply(**kw), check), name="Dexcom G7", keyword="Dexcom")


@pytest.mark.parametrize("check", CHECKS)
def test_garbage_reads_as_could_not_see(check):
    for raw in (None, "", "I think it looks fine!", "{not json", "[1,2]", "<think>hmm</think>"):
        d = cgm_vision.decide(check, cgm_vision.parse(raw, check))
        assert d["status"] == "unsure" and "couldn't see" in d["say"]


def test_unconfident_answers_are_never_ok():
    obs = cgm_vision.parse(reply(confident=False, problem="blur", patch_visible=True, edges_lifted=False), "patch")
    d = cgm_vision.decide("patch", obs)
    assert d["status"] == "unsure" and "blurry" in d["say"]


def test_kit_checks_the_picked_sensor_name():
    assert decide("kit", kit_visible=True, brand_text_visible=True)["status"] == "ok"
    d = decide("kit", kit_visible=True, brand_text_visible=False)
    assert d["status"] == "fix" and "Dexcom G7" in d["say"]
    assert decide("kit", kit_visible=False, brand_text_visible=None)["status"] == "unsure"
    assert cgm_vision.decide("kit", cgm_vision.parse(reply(kit_visible=True, brand_text_visible=False), "kit"))["status"] == "ok"   # no keyword: nothing to match


def test_site_cap_labels_applied_patch_transmitter():
    assert decide("site", skin_visible=True, covered=False, sensor_on_skin=False)["status"] == "ok"
    assert decide("site", skin_visible=True, covered=True, sensor_on_skin=False)["status"] == "fix"
    assert "already" in decide("site", skin_visible=True, covered=False, sensor_on_skin=True)["say"]
    assert decide("cap", applicator_visible=True, open_end_visible=False, cap_on=True)["status"] == "fix"
    assert decide("cap", applicator_visible=True, open_end_visible=True, cap_on=False)["status"] == "ok"
    # found by testing a real inserter photo: "no cap noticed" is not evidence. ok needs the open end seen.
    assert decide("cap", applicator_visible=True, open_end_visible=False, cap_on=False)["status"] == "unsure"
    assert decide("cap", applicator_visible=True, open_end_visible=True, cap_on=None)["status"] == "unsure"
    assert decide("labels", adhesive_visible=True, label_on=True)["status"] == "fix"
    assert decide("applied", applicator_visible=True, flat_on_skin=False)["status"] == "fix"
    assert decide("patch", patch_visible=True, on_skin=True, edges_lifted=True)["status"] == "fix"
    assert decide("patch", patch_visible=True, on_skin=True, edges_lifted=False)["status"] == "ok"
    # a patch that is not on skin (a red circle on a table) must never pass
    assert decide("patch", patch_visible=True, on_skin=False, edges_lifted=False)["status"] == "unsure"
    assert decide("patch", patch_visible=True, on_skin=None, edges_lifted=False)["status"] == "unsure"
    assert decide("transmitter", holder_visible=True, transmitter_snapped=False)["status"] == "fix"


def test_ok_is_only_ever_a_second_check_and_never_a_go_ahead():
    cases = [("kit", dict(kit_visible=True, brand_text_visible=True)), ("site", dict(skin_visible=True, covered=False, sensor_on_skin=False)),
             ("cap", dict(applicator_visible=True, open_end_visible=True, cap_on=False)), ("patch", dict(patch_visible=True, on_skin=True, edges_lifted=False))]
    for check, kw in cases:
        d = decide(check, **kw)
        assert d["status"] == "ok" and "second check" in d["say"]
        for bad in ("safe", "go ahead", "correct", "units", "glucose"):
            assert bad not in d["say"].lower()


def test_tips_never_mention_pens_or_needles():
    assert not any(w in " ".join(cgm_vision.TIPS.values()).lower() for w in ("pen", "needle"))
    assert "pen" not in decide("site", skin_visible=False, covered=None, sensor_on_skin=None, confident=False, problem="cut_off")["say"].lower()


def test_a_wrong_typed_field_reads_as_unknown():
    obs = cgm_vision.parse(json.dumps({"confident": True, "applicator_visible": True, "open_end_visible": True, "cap_on": "no"}), "cap")
    assert obs["cap_on"] is None and cgm_vision.decide("cap", obs)["status"] == "unsure"


def test_prompts_exist_for_every_checkpoint_and_kit_names_the_sensor():
    assert set(cgm_vision.PROMPTS) == set(CHECKS)
    assert '"Dexcom"' in cgm_vision.prompt("kit", "Dexcom") and "{keyword}" not in cgm_vision.prompt("kit", "")
    for c in CHECKS:
        assert "null" in cgm_vision.prompt(c, "x") and "confident" in cgm_vision.prompt(c, "x")
