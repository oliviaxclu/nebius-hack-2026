import json

import pytest

from prime import cites
from prime.tools import TOOL_NAMES, TOOL_SCHEMAS
from tests.conftest import d


def test_schema_matches_methods(loaded):
    _, tb, _ = loaded
    assert TOOL_NAMES == {s["function"]["name"] for s in TOOL_SCHEMAS}
    for name in TOOL_NAMES:
        assert callable(getattr(tb, name)), name
    required = {"get_glucose", "get_medications", "get_insulin_log", "get_meals", "get_wearable_summary", "search_medical_evidence"}
    assert required <= TOOL_NAMES                                              # the six tools in the brief


def test_get_glucose_modes(loaded):
    _, tb, _ = loaded
    s = tb.get_glucose(d(14), d(14))
    assert s["summary"]["n"] == 96 and s["summary"]["tir_70_180_pct"] == 0.0 and s["day_cites"] == [f"day:{d(14)}"]
    h = tb.get_glucose(d(14), d(14), "hourly")
    assert len(h["hourly"]) == 24
    dly = tb.get_glucose(d(9), d(13), "daily")
    assert [x["steroid_mg_today"] for x in dly["daily"]] == [30, 30, 30, 30, 30]
    assert "error" in tb.get_glucose(d(1), d(30), "points")                    # too many points
    assert len(tb.get_glucose(d(14), d(14), "points")["points"]) == 96
    assert "error" in tb.get_glucose(d(1), d(2), "banana")
    assert tb.get_glucose("2020-01-01", "2020-01-02")["found"] is False


def test_get_medications_steroid_status(loaded):
    _, tb, _ = loaded
    m = tb.get_medications(d(10))
    names = {x["name"] for x in m["active_medications"]}
    assert {"Metformin", "Semaglutide", "Insulin glargine", "Prednisone taper"} <= names
    assert m["steroid"]["active_today"] and m["steroid"]["course_day"] == 2 and m["steroid"]["doses_today"][0]["mg"] == 30
    glar = [x for x in tb.get_medications(d(18))["active_medications"] if x["name"] == "Insulin glargine"]
    assert [x["dose"] for x in glar] == ["26 units"]                            # the raised dose is the active row on day 18
    assert tb.get_medications(d(28))["steroid"]["active_today"] is False


def test_get_insulin_log_and_meals_and_wearables(loaded):
    _, tb, _ = loaded
    e = tb.get_insulin_log(d(16))["entries"]
    assert len(e) == 1 and e[0]["units"] == 26 and e[0]["pre_injection_check_done"] is None and "clinic" in e[0]["note"]
    assert tb.get_insulin_log(d(21))["entries"][0]["pre_injection_check_done"] is True
    assert len(tb.get_insulin_log(d(1), d(7))["entries"]) == 7
    meals = tb.get_meals(d(5))["meals"]
    assert len(meals) == 3 and meals[0]["vegetables_protein_first"] is True
    w = tb.get_wearable_summary(d(10))
    assert w["found"] and w["sleep_quality_0_100"] < 60 and w["cite"] == f"day:{d(10)}"
    assert tb.get_wearable_summary("2020-01-01")["found"] is False


def test_search_medical_evidence_contract(loaded):
    _, tb, _ = loaded
    r = tb.search_medical_evidence("why am I high in the afternoon on prednisone")
    top = r["passages"][0]
    assert top["topic"] == "steroid" and top["cite"].startswith("src:") and top["url"].startswith("http") and top["evidence_level"]
    assert r["passages"] == tb.search_medical_evidence("why am I high in the afternoon on prednisone", k=4)["passages"]


def test_episode_context_explains_a_steroid_afternoon(loaded):
    _, tb, _ = loaded
    c = tb.get_episode_context(f"{d(10)}T14:30:00", 6)
    assert c["steroid_last_30h"][-1]["mg"] == 30 and 6 <= c["steroid_last_30h"][-1]["hours_before"] <= 7
    assert c["meals_in_window"] and c["insulin_last_36h"] and c["wearable_today"]["found"]
    assert c["glucose_summary"]["max"] > 200 and c["day_cite"] == f"day:{d(10)}"


def test_find_excursions_context(loaded):
    _, tb, _ = loaded
    r = tb.find_excursions(d(21), d(25), "low")
    assert r["count"] == 5 and all(x["kind"] == "low" for x in r["excursions"])
    assert all(x["context"]["last_insulin"]["units"] == 26 for x in r["excursions"])


def test_visit_summary_is_complete(loaded):
    _, tb, _ = loaded
    v = tb.visit_summary(d(1), d(30))
    assert v["dose_response"]["flagged"] and v["insulin_dose_changes"] == [
        {"date": d(16), "from_units": 18.0, "to_units": 26.0}, {"date": d(25), "from_units": 26.0, "to_units": 20.0}]
    assert len(v["steroid_days"]) == 15 and v["meal_experiment"]["comparable"] and len(v["questions_to_consider"]) == 3
    lows = [x for x in v["lows"] if not x["possible_compression_artifact"]]
    assert len(lows) == 5 and any(x["possible_compression_artifact"] for x in v["lows"])


def test_pre_injection_checklist_has_two_caps_and_valid_sources(loaded):
    conn, tb, _ = loaded
    r = tb.pre_injection_checklist()
    text = " ".join(s["say"] for s in r["steps"]).lower()
    assert "two caps" in text and "outer cap" in text and "inner cap" in text and "safety test" in text and "count" in text
    for s in r["steps"]:
        for c in s.get("src", []):
            assert c and cites.describe(conn, c), c                                # every source id resolves
    assert len(r["teach_back_questions"]) == 3


def test_log_insulin_readback_and_dose_sanity(loaded):
    _, tb, _ = loaded
    ok = tb.log_insulin(20, pre_injection_check_done=True)
    assert ok["logged"] and "20 units" in ok["readback"] and "warning" not in ok
    big = tb.log_insulin(50)
    assert big["logged"] and "STOP" in big["warning"] and "care team" in big["warning"]       # >=1.5x recent median
    assert tb.log_insulin(0)["logged"] is False and tb.log_insulin(150)["logged"] is False
    assert tb.get_insulin_log("2026-10-13")["entries"][0]["pre_injection_check_done"] is True


def test_log_meal_journal_reminder(loaded, tmp_path):
    _, tb, _ = loaded
    assert tb.log_meal("oatmeal", carbs_g=45)["logged"]
    assert tb.add_journal("felt dizzy at 3am")["saved"]
    assert tb.search_journal("dizzy")["entries"][0]["text"].startswith("felt dizzy")
    r = tb.create_reminder("Pen check", "2026-10-14T21:00:00", repeat="daily", kind="medication")
    assert r["saved"] and "RRULE:FREQ=DAILY" in tb.ics_path.read_text()
    assert tb.list_reminders()["reminders"][0]["title"] == "Pen check"


def test_dispatch_errors_do_not_crash(loaded):
    _, tb, _ = loaded
    assert "error" in json.loads(tb.dispatch("nope", {}))
    assert "error" in json.loads(tb.dispatch("create_reminder", {"title": "x", "due": "not-a-date"}))
    assert "error" in json.loads(tb.dispatch("get_glucose", {"start": "2026-09-14"}))          # missing arg


def test_every_cite_in_every_tool_output_resolves(loaded):
    conn, tb, _ = loaded
    calls = [("get_glucose", {"start": d(9), "end": d(13), "mode": "daily"}), ("get_medications", {"date": d(10)}),
             ("get_insulin_log", {"date": d(13), "end_date": d(21)}), ("get_meals", {"date": d(5)}), ("get_wearable_summary", {"date": d(10)}),
             ("search_medical_evidence", {"question": "steroid dawn pen glp1"}), ("get_episode_context", {"ts": f"{d(14)}T10:00:00"}),
             ("find_excursions", {"start": d(1), "end": d(30)}), ("check_dose_response", {"start": d(1), "end": d(30)}),
             ("visit_summary", {"start": d(1), "end": d(30)}), ("pre_injection_checklist", {})]
    total = 0
    for name, args in calls:
        out = tb.dispatch(name, args)
        for c in cites.find_any(out):
            total += 1
            assert cites.describe(conn, c) is not None, (name, c)
    assert total > 100
