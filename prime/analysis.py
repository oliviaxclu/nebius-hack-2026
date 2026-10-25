"""Deterministic glucose analytics. Code computes the numbers; the language model only explains them.

Thresholds below are HEURISTICS for a demo, not validated clinical cutoffs.
"""
from __future__ import annotations

import sqlite3
import statistics as st
from datetime import date, datetime, timedelta

LOW, VLOW, HIGH, VHIGH = 70.0, 54.0, 180.0, 250.0        # consensus bands (mg/dL)
FASTING_FROM, FASTING_TO = "05:00", "07:00"
FASTING_DELTA_FLAG = 35.0     # mg/dL above this person's own reference fasting level
MIN_RUN_DAYS = 3              # consecutive mornings before we flag a pattern
ESCALATION_RATIO = 1.2        # logged dose >= 120% of reference dose counts as escalated
ARTIFACT_SLOPE = 1.2          # mg/dL per minute, steep entry AND exit => suspect compression low
INTERVAL_MIN = 15

LIMITS = [
    "Thresholds are demo heuristics (fasting 35+ mg/dL above your own reference for 3+ mornings), not validated clinical cutoffs.",
    "This shows the glucose pattern is unusual compared with your own reference days; it cannot confirm whether insulin was delivered.",
    "Sensor error, illness or infection, missed or mistimed doses, insulin storage problems, a different steroid dose than expected, "
    "and large diet changes can look similar.",
]
SAFE_NEXT_STEPS = [
    "Do not change, repeat or add insulin on your own because of this pattern.",
    "Contact your care team today and share this summary.",
    "If your pen setup might be off, go through the pre-injection check with a helper or your care team.",
    "If glucose is very high with nausea, vomiting, belly pain or fast breathing, or you feel faint or confused, seek urgent care.",
]


def P(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _range(start: str, end: str) -> tuple[str, str]:
    s = start if "T" in start else start + "T00:00:00"
    e = end if "T" in end else end + "T23:59:59"
    return s, e


def read_glucose(conn: sqlite3.Connection, start: str, end: str) -> list[tuple[datetime, float]]:
    s, e = _range(start, end)
    rows = conn.execute("SELECT ts, mgdl FROM glucose WHERE ts >= ? AND ts <= ? ORDER BY ts", (s, e)).fetchall()
    return [(P(r["ts"]), r["mgdl"]) for r in rows]


def summarize(points: list[tuple[datetime, float]]) -> dict:
    if not points:
        return {"n": 0}
    v = [g for _, g in points]
    n = len(v)
    mean = sum(v) / n
    sd = st.pstdev(v) if n > 1 else 0.0
    pct = lambda cond: round(100 * sum(1 for g in v if cond(g)) / n, 1)  # noqa: E731
    return {"n": n, "hours": round(n * INTERVAL_MIN / 60, 1), "mean": round(mean, 1), "sd": round(sd, 1),
            "cv_pct": round(100 * sd / mean, 1) if mean else None, "min": min(v), "max": max(v),
            "tir_70_180_pct": pct(lambda g: LOW <= g <= HIGH), "below_70_pct": pct(lambda g: g < LOW),
            "below_54_pct": pct(lambda g: g < VLOW), "above_180_pct": pct(lambda g: g > HIGH),
            "above_250_pct": pct(lambda g: g > VHIGH)}


def gaps(points, max_min: int = 30) -> list[dict]:
    out = []
    for (a, _), (b, _) in zip(points, points[1:]):
        mins = (b - a).total_seconds() / 60
        if mins > max_min:
            out.append({"from": a.isoformat(timespec="minutes"), "to": b.isoformat(timespec="minutes"), "minutes": int(mins)})
    return out


def hourly(points) -> list[dict]:
    b: dict[str, list[float]] = {}
    for t, g in points:
        b.setdefault(t.strftime("%Y-%m-%dT%H:00"), []).append(g)
    return [{"hour": k, "mean": round(sum(v) / len(v), 1), "min": min(v), "max": max(v), "n": len(v)} for k, v in sorted(b.items())]


def excursions(points, high: float = HIGH, low: float = LOW) -> list[dict]:
    """Contiguous highs (>=30 min observed) and lows (>=15 min observed, i.e. 2+ readings); lows get a compression-artifact flag."""
    out, i, n = [], 0, len(points)
    kind_of = lambda g: "high" if g > high else ("low" if g < low else None)  # noqa: E731
    while i < n:
        k = kind_of(points[i][1])
        if k is None:
            i += 1
            continue
        j = i
        while j + 1 < n and kind_of(points[j + 1][1]) == k and (points[j + 1][0] - points[j][0]).total_seconds() <= 30 * 60:
            j += 1
        seg = points[i:j + 1]
        span = (seg[-1][0] - seg[0][0]).total_seconds() / 60          # minutes actually observed between first and last reading
        dur = span + INTERVAL_MIN
        if span >= (30 if k == "high" else 15):                       # lows need 2+ consecutive readings, highs 3+ (15-min data)
            vals = [g for _, g in seg]
            ext = max(vals) if k == "high" else min(vals)
            ex = {"kind": k, "start": seg[0][0].isoformat(timespec="minutes"), "end": seg[-1][0].isoformat(timespec="minutes"),
                  "duration_min": int(dur), "peak_or_nadir": ext,
                  "level": ("level2" if (ext > VHIGH if k == "high" else ext < VLOW) else "level1")}
            if k == "low":
                entry = exit_ = None
                if i > 0:
                    entry = (seg[0][1] - points[i - 1][1]) / max(1.0, (seg[0][0] - points[i - 1][0]).total_seconds() / 60)
                if j + 1 < n:
                    exit_ = (points[j + 1][1] - seg[-1][1]) / max(1.0, (points[j + 1][0] - seg[-1][0]).total_seconds() / 60)
                ex["entry_slope"] = None if entry is None else round(entry, 2)
                ex["exit_slope"] = None if exit_ is None else round(exit_, 2)
                ex["possible_compression_artifact"] = bool(
                    dur <= 90 and entry is not None and exit_ is not None and entry <= -ARTIFACT_SLOPE and exit_ >= ARTIFACT_SLOPE)
            out.append(ex)
        i = j + 1
    return out


# ---------------------------------------------------------------- context lookups
def last_insulin_before(conn, ts: datetime, within_h: int = 30) -> dict | None:
    r = conn.execute("SELECT * FROM insulin_log WHERE ts <= ? AND ts >= ? ORDER BY ts DESC LIMIT 1",
                     (ts.isoformat(timespec="seconds"), (ts - timedelta(hours=within_h)).isoformat(timespec="seconds"))).fetchone()
    return dict(r) if r else None


def steroid_before(conn, ts: datetime, within_h: int = 30) -> dict | None:
    r = conn.execute("SELECT * FROM steroid_doses WHERE ts <= ? AND ts >= ? ORDER BY ts DESC LIMIT 1",
                     (ts.isoformat(timespec="seconds"), (ts - timedelta(hours=within_h)).isoformat(timespec="seconds"))).fetchone()
    if not r:
        return None
    return {"cite": f"ste:{r['id']}", "drug": r["drug"], "dose_mg": r["dose_mg"], "ts": r["ts"],
            "hours_since": round((ts - P(r["ts"])).total_seconds() / 3600, 1)}


def meal_before(conn, ts: datetime, within_h: float = 4) -> dict | None:
    r = conn.execute("SELECT * FROM meals WHERE ts <= ? AND ts >= ? ORDER BY ts DESC LIMIT 1",
                     (ts.isoformat(timespec="seconds"), (ts - timedelta(hours=within_h)).isoformat(timespec="seconds"))).fetchone()
    if not r:
        return None
    return {"cite": f"meal:{r['id']}", "label": r["label"], "ts": r["ts"], "carbs_g": r["carbs_g"],
            "minutes_before": int((ts - P(r["ts"])).total_seconds() / 60)}


def annotate(conn, ex: dict) -> dict:
    t0 = P(ex["start"])
    ins = last_insulin_before(conn, t0)
    ex = dict(ex)
    ex["context"] = {
        "meal_before": meal_before(conn, t0),
        "steroid_before": steroid_before(conn, t0),
        "last_insulin": None if not ins else {"cite": f"ins:{ins['id']}", "units": ins["units"], "ts": ins["ts"], "steps_checked": ins["steps_checked"]},
    }
    ex["day_cite"] = f"day:{t0.date().isoformat()}"
    return ex


# ---------------------------------------------------------------- per-day features
def day_features(conn, d: date) -> dict | None:
    ds = d.isoformat()
    pts = read_glucose(conn, ds, ds)
    if not pts:
        return None
    t = lambda a, b: [g for tt, g in pts if a <= tt.strftime("%H:%M") <= b]  # noqa: E731
    fast = t(FASTING_FROM, FASTING_TO)
    aft = [g for tt, g in pts if "12:00" <= tt.strftime("%H:%M") < "20:00"]
    night = t("00:00", "05:00")
    day5 = datetime.combine(d, datetime.min.time()) + timedelta(hours=5)
    ins = last_insulin_before(conn, day5, within_h=17)       # the bedtime dose before this morning
    ste_today = conn.execute("SELECT COALESCE(SUM(dose_mg),0) m FROM steroid_doses WHERE substr(ts,1,10)=?", (ds,)).fetchone()["m"]
    ste_prev = steroid_before(conn, day5, within_h=48)
    ste_prev24 = steroid_before(conn, day5, within_h=24)
    s = summarize(pts)
    return {
        "date": ds, "cite": f"day:{ds}", "n": len(pts),
        "fasting": round(st.median(fast), 1) if len(fast) >= 3 else None,
        "predawn_min": min(night) if night else None,
        "afternoon_mean": round(sum(aft) / len(aft), 1) if aft else None,
        "mean": s["mean"], "tir": s["tir_70_180_pct"], "below_70_pct": s["below_70_pct"], "max": s["max"], "min": s["min"],
        "units_prev_night": None if not ins else ins["units"],
        "ins_cite": None if not ins else f"ins:{ins['id']}",
        "steps_checked": None if not ins else ins["steps_checked"],
        "steroid_mg_today": ste_today,
        "steroid_in_prev_48h": ste_prev is not None or ste_today > 0,
        "steroid_prev_24h": ste_prev24 is not None,
    }


def reference_baseline(conn, first_day: date, last_day: date) -> dict | None:
    """Reference = earliest run of days before any steroid exposure, with logged insulin and a fasting reading."""
    days, d = [], first_day
    while d <= last_day:
        f = day_features(conn, d)
        if f and f["steroid_in_prev_48h"]:
            break
        if f and f["fasting"] is not None and f["units_prev_night"] is not None:
            days.append(f)
        d += timedelta(days=1)
    if len(days) < 4:
        return None
    return {"days": [x["date"] for x in days], "fasting": round(st.median(x["fasting"] for x in days), 1),
            "afternoon_mean": round(st.median(x["afternoon_mean"] for x in days if x["afternoon_mean"] is not None), 1),
            "units": st.median(x["units_prev_night"] for x in days)}


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    out, i = [], 0
    while i < len(flags):
        if flags[i]:
            j = i
            while j + 1 < len(flags) and flags[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def check_dose_response(conn, start: str, end: str) -> dict:
    s_day, e_day = date.fromisoformat(start[:10]), date.fromisoformat(end[:10])
    row = conn.execute("SELECT MIN(substr(ts,1,10)) a, MAX(substr(ts,1,10)) b FROM glucose").fetchone()
    if not row["a"]:
        return {"available": False, "reason": "no glucose data"}
    ref = reference_baseline(conn, date.fromisoformat(row["a"]), date.fromisoformat(row["b"]))
    if ref is None:
        return {"available": False, "reason": "Need at least 4 early days with logged insulin and no steroid exposure to build a personal reference.",
                "limits": LIMITS}
    feats, d = [], s_day
    while d <= e_day:
        f = day_features(conn, d)
        if f:
            f["fasting_delta"] = None if f["fasting"] is None else round(f["fasting"] - ref["fasting"], 1)
            f["afternoon_delta"] = None if f["afternoon_mean"] is None else round(f["afternoon_mean"] - ref["afternoon_mean"], 1)
            feats.append(f)
        d += timedelta(days=1)
    flags = [f["fasting_delta"] is not None and f["fasting_delta"] >= FASTING_DELTA_FLAG for f in feats]

    # Steroid-only comparison: mornings after a steroid dose, not flagged, with a logged dose close to the reference dose.
    steroid_unflagged = [f["fasting_delta"] for f, fl in zip(feats, flags)
                         if not fl and f["fasting_delta"] is not None and f["steroid_prev_24h"]
                         and f["units_prev_night"] is not None and abs(f["units_prev_night"] - ref["units"]) <= 0.1 * ref["units"]]
    steroid_ref = round(st.median(steroid_unflagged), 1) if len(steroid_unflagged) >= 2 else None

    patterns = []
    for a, b in _runs(flags):
        if b - a + 1 < MIN_RUN_DAYS:
            continue
        run = feats[a:b + 1]
        units = [f["units_prev_night"] for f in run if f["units_prev_night"] is not None]
        mean_delta = round(sum(f["fasting_delta"] for f in run) / len(run), 1)
        escalated_days = [f for f in run if f["units_prev_night"] and f["units_prev_night"] >= ESCALATION_RATIO * ref["units"]]
        early = [f for f in run if f not in escalated_days]
        no_resp = None
        if escalated_days and early:
            m_early = sum(f["fasting_delta"] for f in early) / len(early)
            m_esc = sum(f["fasting_delta"] for f in escalated_days) / len(escalated_days)
            no_resp = bool(m_esc >= 0.8 * m_early)   # improved by less than 20%
        nights_min = [f["predawn_min"] for f in run if f["predawn_min"] is not None]
        night_lows = sum(1 for m in nights_min if m < LOW)
        after = feats[b + 1:]
        recovered = next((f for f in after if f["fasting_delta"] is not None and f["fasting_delta"] < 0.5 * FASTING_DELTA_FLAG), None)
        post_lows = []
        if recovered:
            lo_start = recovered["date"]
            lo_end = (date.fromisoformat(lo_start) + timedelta(days=7)).isoformat()
            post_lows = [annotate(conn, x) for x in excursions(read_glucose(conn, lo_start, lo_end)) if x["kind"] == "low"]
        ratio = None if not steroid_ref or steroid_ref <= 0 else round(mean_delta / steroid_ref, 1)
        confidence = "higher" if (ratio and ratio >= 2.5) or (no_resp and mean_delta >= 2 * FASTING_DELTA_FLAG) else "lower"
        hyps = [
            {"name": "insulin did not have its usual effect (for example, not fully delivered)",
             "for": [f"Mornings ran {mean_delta:+.0f} mg/dL vs your own reference ({ref['fasting']:.0f}) for {len(run)} days while the log shows the usual or a higher dose each night."]
                    + ([f"The logged dose rose to {max(units):.0f} units (reference {ref['units']:.0f}) without fasting glucose improving."] if no_resp else []),
             "against": [] if night_lows == 0 else [f"{night_lows} night(s) in this stretch dipped below 70 mg/dL."],
             "how_to_check": ["Go through the pen check out loud: both needle caps off, safety test shows insulin at the tip, dose dialed to the clicks.",
                              "Ask the care team or pharmacist to watch a dose being given."]},
            {"name": "steroid effect alone",
             "for": ["Steroid doses were active on these days."],
             "against": ([f"On your own steroid days outside this stretch, fasting glucose was only about {steroid_ref:+.0f} mg/dL vs reference, "
                          f"about {ratio}x smaller than during this stretch."] if steroid_ref is not None else
                         ["Steroids usually raise afternoon and evening glucose more than fasting glucose; fasting rose as much as or more than the afternoon here."
                          if all(f["afternoon_delta"] is not None for f in run) and mean_delta >= sum(f["afternoon_delta"] for f in run) / len(run) * 0.7 else
                          "No steroid-only comparison days were available."]),
             "how_to_check": ["Compare fasting glucose on days with a steroid dose but a confirmed correct injection."]},
            {"name": "waning or mistimed insulin",
             "for": ["Mornings were high."],
             "against": ["The logged dose time was consistent each night."],
             "how_to_check": ["Check the time of each dose against the clock; ask whether the dose was moved earlier or later."]},
            {"name": "Somogyi rebound after a night-time low",
             "for": [] if night_lows == 0 else [f"{night_lows} night(s) had a low before morning."],
             "against": ["No glucose below 70 mg/dL between midnight and 5 AM during this stretch."] if night_lows == 0 else [],
             "how_to_check": ["Look for lows between midnight and 5 AM before the high mornings."]},
            {"name": "sensor problem, illness or a big diet change",
             "for": [], "against": ["The pattern is steady across days rather than a one-off jump."],
             "how_to_check": ["Confirm a couple of readings with a fingerstick meter; ask about fever, infection or new foods."]},
        ]
        pat = {
            "type": "fasting_high_despite_logged_insulin",
            "from": run[0]["date"], "to": run[-1]["date"], "days": len(run),
            "fasting_delta_mean": mean_delta, "fasting_delta_max": max(f["fasting_delta"] for f in run),
            "reference_fasting": ref["fasting"], "reference_units": ref["units"],
            "logged_units_range": [min(units), max(units)] if units else None,
            "dose_escalated": bool(escalated_days), "escalation_without_response": no_resp,
            "steroid_only_fasting_delta": steroid_ref, "ratio_vs_steroid_only": ratio,
            "confidence": confidence,
            "day_cites": [f["cite"] for f in run], "insulin_cites": [f["ins_cite"] for f in run if f["ins_cite"]],
            "recovered_on": None if not recovered else recovered["date"],
            "steps_checked_at_recovery": None if not recovered else recovered["steps_checked"],
            "lows_after_recovery": [{"start": x["start"], "level": x["level"], "nadir": x["peak_or_nadir"],
                                     "possible_compression_artifact": x["possible_compression_artifact"],
                                     "steroid_before": x["context"]["steroid_before"],
                                     "last_insulin": x["context"]["last_insulin"]} for x in post_lows],
            "hypotheses": hyps,
        }
        if pat["dose_escalated"] and post_lows and any(not x["possible_compression_artifact"] for x in post_lows):
            pat["risk_note"] = ("The dose was raised while the usual effect seemed to be missing. Once delivery works and steroids are tapering, "
                                "the same higher dose can cause lows. Raise this with the care team before the next dose change.")
        patterns.append(pat)

    return {"available": True, "range": [s_day.isoformat(), e_day.isoformat()],
            "reference": {"fasting": ref["fasting"], "afternoon_mean": ref["afternoon_mean"], "units": ref["units"], "days": ref["days"]},
            "days": [{k: f[k] for k in ("date", "cite", "fasting", "fasting_delta", "afternoon_mean", "afternoon_delta",
                                        "units_prev_night", "ins_cite", "steps_checked", "steroid_mg_today", "tir", "predawn_min")} for f in feats],
            "patterns": patterns, "flagged": bool(patterns), "limits": LIMITS,
            "safe_next_steps": SAFE_NEXT_STEPS if patterns else []}


# ---------------------------------------------------------------- meal experiments
def meal_rise(conn, meal_ts: datetime) -> float | None:
    pts = read_glucose(conn, meal_ts.isoformat(timespec="seconds"), (meal_ts + timedelta(hours=3)).isoformat(timespec="seconds"))
    pre = conn.execute("SELECT mgdl FROM glucose WHERE ts <= ? AND ts >= ? ORDER BY ts DESC LIMIT 1",
                       (meal_ts.isoformat(timespec="seconds"), (meal_ts - timedelta(minutes=25)).isoformat(timespec="seconds"))).fetchone()
    if not pts or not pre:
        return None
    return round(max(g for _, g in pts) - pre["mgdl"], 1)


def meal_experiment(conn, start: str, end: str, slot: str = "breakfast") -> dict:
    """Compare meals eaten vegetables/protein-first vs. carbs-first/mixed, matched on carbohydrate grams, non-steroid days only."""
    s, e = _range(start, end)
    rows = conn.execute("SELECT * FROM meals WHERE ts>=? AND ts<=? AND notes=? ORDER BY ts", (s, e, slot)).fetchall()
    items = []
    for r in rows:
        t = P(r["ts"])
        if steroid_before(conn, t, within_h=24):
            continue                                        # keep steroid days out of the comparison
        rise = meal_rise(conn, t)
        if rise is not None:
            items.append({"cite": f"meal:{r['id']}", "label": r["label"], "date": r["ts"][:10], "rise": rise,
                          "carbs_g": r["carbs_g"], "protein_g": r["protein_g"], "veg_protein_first": int(r["carbs_last"] or 0)})
    first = [x for x in items if x["veg_protein_first"]]
    out = {"slot": slot, "vegetables_protein_first": first, "comparable": False,
           "caveat": "A few meals on a few days. Foods, sleep and activity differ between days, so this is a hint, not proof."}
    if first:
        target = sum(x["carbs_g"] for x in first) / len(first)
        base = [x for x in items if not x["veg_protein_first"] and abs(x["carbs_g"] - target) <= 8]
        mean = lambda xs: None if not xs else round(sum(x["rise"] for x in xs) / len(xs), 1)  # noqa: E731
        out.update({"carbs_first_or_mixed_matched": base, "mean_rise_veg_protein_first": mean(first),
                    "mean_rise_carbs_first_or_mixed": mean(base), "comparable": bool(base)})
    return out
