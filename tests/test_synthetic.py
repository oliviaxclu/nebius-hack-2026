import statistics as st

from prime import analysis as A
from prime import db, synthetic
from tests.conftest import TODAY, d, make


def fasting(conn, n):
    return A.day_features(conn, __import__("datetime").date.fromisoformat(d(n)))["fasting"]


def test_shape_and_determinism(tmp_path):
    c1, _, d1 = make(tmp_path, name="a.db")
    c2, _, d2 = make(tmp_path, name="b.db")
    assert d1["glucose"] == d2["glucose"] and len(d1["glucose"]) > 2800        # 30 days at 15 min minus gaps
    assert d1["glucose"][0]["ts"] == f"{d(1)}T00:00:00" and d1["glucose"][-1]["ts"].startswith(d(30))
    n = c1.execute("SELECT COUNT(*) FROM insulin_log").fetchone()[0]
    assert n == 30 and c1.execute("SELECT COUNT(*) FROM steroid_doses").fetchone()[0] == 15


def test_everything_the_brief_asked_for_exists(loaded):
    conn, _, _ = loaded
    for table in ("glucose", "medications", "steroid_doses", "insulin_log", "meals", "wearable_daily", "profile", "evidence"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] > 0, table
    prof = db.load_profile(conn)
    assert prof["voice_first"] == "true" and "low vision" in prof["vision"]


def test_designed_fasting_levels(loaded):
    conn, _, _ = loaded
    baseline = st.median(fasting(conn, n) for n in range(1, 9))
    assert 115 <= baseline <= 135
    steroid_only = [fasting(conn, n) for n in (10, 11, 12)]                    # steroids, insulin still delivered
    assert all(f - baseline < 35 for f in steroid_only)                        # fasting stays near normal on steroids alone
    failure = [fasting(conn, n) for n in range(13, 21)]                        # mornings after undelivered doses
    assert all(f - baseline >= 55 for f in failure)
    assert all(fasting(conn, n) - baseline < 15 for n in (26, 27, 29, 30))     # back to normal later


def test_afternoon_steroid_pattern(loaded):
    conn, _, _ = loaded
    f9 = A.day_features(conn, __import__("datetime").date.fromisoformat(d(9)))
    f8 = A.day_features(conn, __import__("datetime").date.fromisoformat(d(8)))
    assert f9["afternoon_mean"] - f8["afternoon_mean"] > 40                     # steroid day: afternoon much higher
    assert abs(f9["fasting"] - f8["fasting"]) < 20                               # but fasting is not


def test_taper_lows_and_artifact(loaded):
    conn, _, data = loaded
    pts = A.read_glucose(conn, d(1), d(30))
    lows = [x for x in A.excursions(pts) if x["kind"] == "low"]
    real = [x for x in lows if not x["possible_compression_artifact"]]
    art = [x for x in lows if x["possible_compression_artifact"]]
    real_days = {x["start"][:10] for x in real}
    assert real_days == {d(n) for n in range(21, 26)}                           # nights after delivery restored and taper
    assert any(x["level"] == "level2" for x in real)
    assert len(art) == 1 and art[0]["start"][:10] == data["truth"]["compression_artifact_morning"]
    assert art[0]["duration_min"] <= 90


def test_counterfactual_has_no_failure_signature(no_failure):
    conn, _, data = no_failure
    assert data["truth"]["undelivered_dose_dates"] == []
    assert all(fasting(conn, n) < 170 for n in range(10, 21))                   # no jump to ~200


def test_gaps_exist_and_are_reported(loaded):
    conn, _, _ = loaded
    pts = A.read_glucose(conn, d(5), d(5))
    assert A.gaps(pts) and A.gaps(pts)[0]["minutes"] >= 120


def test_ground_truth_file(tmp_path):
    _, _, data = make(tmp_path)
    p = tmp_path / "truth.json"
    synthetic.write_truth(p, data)
    t = __import__("json").loads(p.read_text())
    assert t["affected_mornings"] == [d(n) for n in range(13, 21)] and t["dose_raised_on"] == d(16)
