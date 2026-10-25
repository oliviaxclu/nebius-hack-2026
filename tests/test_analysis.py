from datetime import datetime, timedelta

from prime import analysis as A
from tests.conftest import d


def test_summary_bands():
    base = datetime(2026, 1, 1)
    vals = [60, 100, 100, 100, 200, 300, 50, 100, 100, 100]
    s = A.summarize([(base + timedelta(minutes=15 * i), v) for i, v in enumerate(vals)])
    assert s["n"] == 10 and s["tir_70_180_pct"] == 60.0 and s["below_70_pct"] == 20.0
    assert s["below_54_pct"] == 10.0 and s["above_180_pct"] == 20.0 and s["above_250_pct"] == 10.0


def test_excursions_basic_and_min_duration():
    base = datetime(2026, 1, 1)
    vals = [100, 100, 200, 210, 220, 100, 60, 100, 100, 190, 100]       # one high (45 min), one 1-point low (too short), one 1-point high
    ex = A.excursions([(base + timedelta(minutes=15 * i), v) for i, v in enumerate(vals)])
    assert [e["kind"] for e in ex] == ["high"] and ex[0]["peak_or_nadir"] == 220 and ex[0]["level"] == "level1"


def test_compression_artifact_vs_gradual_low():
    base = datetime(2026, 1, 1, 2)
    steep = [100, 100, 75, 50, 52, 55, 80, 100, 100]
    gradual = [100, 92, 85, 78, 72, 66, 62, 60, 62, 66, 72, 80, 90]
    a = [e for e in A.excursions([(base + timedelta(minutes=15 * i), v) for i, v in enumerate(steep)]) if e["kind"] == "low"]
    g = [e for e in A.excursions([(base + timedelta(minutes=15 * i), v) for i, v in enumerate(gradual)]) if e["kind"] == "low"]
    assert a and a[0]["possible_compression_artifact"] is True
    assert g and g[0]["possible_compression_artifact"] is False


def test_dose_response_finds_exact_window(loaded):
    conn, _, data = loaded
    r = A.check_dose_response(conn, d(1), d(30))
    assert r["available"] and r["flagged"] and len(r["patterns"]) == 1
    p = r["patterns"][0]
    assert (p["from"], p["to"]) == (d(13), d(20))                                  # == truth["affected_mornings"]
    assert [d_ for d_ in data["truth"]["affected_mornings"]] == [d(n) for n in range(13, 21)]
    assert p["confidence"] == "higher" and p["dose_escalated"] and p["escalation_without_response"]
    assert p["steroid_only_fasting_delta"] is not None and p["ratio_vs_steroid_only"] >= 2.5
    assert p["recovered_on"] == d(21) and p["steps_checked_at_recovery"] == 1
    assert p["logged_units_range"] == [18.0, 26.0]


def test_hypotheses_are_data_driven(loaded):
    conn, _, _ = loaded
    p = A.check_dose_response(conn, d(1), d(30))["patterns"][0]
    h = {x["name"]: x for x in p["hypotheses"]}
    assert len(h) == 5
    steroid = h["steroid effect alone"]
    assert any("smaller" in s for s in steroid["against"])                         # own steroid-only mornings were much smaller
    somogyi = h["Somogyi rebound after a night-time low"]
    assert somogyi["for"] == [] and somogyi["against"]                             # no night lows before the high mornings
    assert any("did not have its usual effect" in k for k in h)


def test_risk_note_when_dose_raised_then_lows(loaded):
    conn, _, _ = loaded
    p = A.check_dose_response(conn, d(1), d(30))["patterns"][0]
    assert "risk_note" in p and "lows" in p["risk_note"]
    real = [x for x in p["lows_after_recovery"] if not x["possible_compression_artifact"]]
    assert len(real) >= 4


def test_no_flag_without_failure(no_failure):
    conn, _, _ = no_failure
    r = A.check_dose_response(conn, d(1), d(30))
    assert r["available"] and r["flagged"] is False and r["patterns"] == [] and r["safe_next_steps"] == []


def test_limits_always_present_and_safe_steps_never_dose_advice(loaded):
    conn, _, _ = loaded
    r = A.check_dose_response(conn, d(1), d(30))
    assert len(r["limits"]) >= 3
    for s in r["safe_next_steps"]:
        assert "do not change" in s.lower() or "contact" in s.lower() or "pre-injection" in s.lower() or "urgent" in s.lower()


def test_needs_reference_days(tmp_path):
    from tests.conftest import make
    from prime import synthetic
    conn, _, _ = make(tmp_path, synthetic.Scenario(steroid_course=[(1, 6, 30.0)]), "early.db")   # steroids from day 1 => no clean baseline
    r = A.check_dose_response(conn, d(1), d(30))
    assert r["available"] is False and "reference" in r["reason"]


def test_meal_experiment_matched_and_directional(loaded):
    conn, _, _ = loaded
    m = A.meal_experiment(conn, d(1), d(30))
    assert m["comparable"] and len(m["vegetables_protein_first"]) == 2
    assert m["mean_rise_veg_protein_first"] < m["mean_rise_carbs_first_or_mixed"]
    assert "not proof" in m["caveat"]
