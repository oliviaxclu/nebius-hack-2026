"""Synthetic longitudinal patient: 30 days of Libre-style CGM plus everything around it.

FICTIONAL. Built for testing and demos; contains no real patient data. The glucose model is a toy
(baseline + meals + steroid curve + dawn rise + basal insulin + sleep + noise); it is NOT
physiologically validated. Its job is to produce *designed episodes with known ground truth*, so the
analysis code and the agent can be tested against them.

Designed episodes (day numbers are 1..30; the window ends yesterday):
  1-8    baseline: modest meal spikes, small dawn rise, fasting ~120s
  3-6    meal experiments (toast vs eggs/greens first); 7-8 post-dinner walks
  9-23   oral prednisone course (30 mg x5, 20 mg x5, 10 mg x5): afternoon/evening highs
  12-19  SILENT DELIVERY FAILURE: bedtime basal dose is logged but not delivered
         -> mornings 13-20 run high; the logged dose is raised on day 16 with no response
  20     delivery restored (pre-injection check adopted from this night on)
  21-25  taper + higher basal dose now actually working -> nocturnal lows
  28     one compression-low artifact (V-shaped, ~45 min, no symptoms)
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

PATIENT = {"given": "Ray", "family": "Hale", "dob": "1957-06-14", "mrn": "MRN-0172264",
           "phone": "415-555-0188", "email": "ray.hale@example.com"}

PROFILE = {
    "vision": "low vision: cannot reliably see needle caps, the dose window, or charts",
    "voice_first": "true",
    "read_aloud": "true",
    "tts_rate": "0.95",
    "large_text": "true",
    "high_contrast": "true",
    "confirm_by_readback": "true",
    "glucose_units": "mg/dL",
    "insulin_device": "prefilled basal insulin pen (needle has an outer cap and an inner cap)",
    "pen": "lantus-solostar",
}

COURSE = [(9, 13, 30.0), (14, 18, 20.0), (19, 23, 10.0)]   # (first day, last day, mg prednisone)


@dataclass
class Scenario:
    failure_days: tuple[int, int] | None = (12, 19)   # bedtime-dose days that are NOT delivered
    seed: int = 7
    n_days: int = 30
    steroid_course: list = field(default_factory=lambda: list(COURSE))

    def units(self, d: int) -> float:
        if d <= 15:
            return 18.0
        if d <= 24:
            return 26.0
        return 20.0

    def delivered(self, d: int) -> bool:
        if self.failure_days is None:
            return True
        return not (self.failure_days[0] <= d <= self.failure_days[1])

    def steroid_mg(self, d: int) -> float:
        for a, b, mg in self.steroid_course:
            if a <= d <= b:
                return mg
        return 0.0


def _bell(x: float, mu: float, sigma: float) -> float:
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def _steroid_curve(hours_since: float, mg: float) -> float:
    """Afternoon-weighted curve: onset ~2 h, peak ~5 h, mostly gone by ~16 h."""
    if hours_since < 0 or hours_since > 30:
        return 0.0
    x = hours_since / 5.0
    return (mg / 30.0) * x * x * math.exp(2 * (1 - x))


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S")


BREAKFASTS = [("oatmeal with berries", 48, 9, 6), ("yogurt and granola", 40, 14, 3),
              ("scrambled eggs and toast", 30, 16, 3), ("cereal with milk", 52, 8, 3)]
LUNCHES = [("chicken sandwich", 52, 28, 4), ("lentil soup and bread", 55, 18, 10),
           ("rice bowl with tofu", 62, 20, 6), ("turkey wrap and fruit", 48, 24, 5)]
DINNERS = [("pasta with meatballs", 68, 30, 5), ("baked fish, potatoes, beans", 50, 34, 8),
           ("stir-fry with rice", 60, 26, 6), ("chicken, rice and salad", 55, 36, 6)]


def build(today: date | None = None, scenario: Scenario | None = None) -> dict:
    sc = scenario or Scenario()
    rnd = random.Random(sc.seed)
    today = today or date.today()
    first = today - timedelta(days=sc.n_days)               # day 1
    day_date = {d: first + timedelta(days=d - 1) for d in range(1, sc.n_days + 1)}
    dstr = lambda d: day_date[d].isoformat()                # noqa: E731

    # ---------------- wearables ----------------
    wearable = []
    for d in range(1, sc.n_days + 1):
        poor = d in (10, 14, 17)                            # steroid-related poor sleep nights
        wearable.append({
            "date": dstr(d),
            "sleep_h": round(rnd.uniform(4.6, 5.3) if poor else rnd.gauss(6.9, 0.45), 1),
            "sleep_quality": rnd.randint(38, 52) if poor else rnd.randint(66, 86),
            "steps": int(rnd.gauss(4300, 800)),
            "active_min": max(5, int(rnd.gauss(28, 8))),
            "resting_hr": int(rnd.gauss(72, 2.5)),
            "walk_after_dinner_min": 12 if (d in (7, 8) or d >= 26) else rnd.choice([0, 0, 0, 5]),
        })
    wear_by_date = {w["date"]: w for w in wearable}

    # ---------------- meals ----------------
    meals = []
    for d in range(1, sc.n_days + 1):
        for slot, pool, hh, mm_jit in (("breakfast", BREAKFASTS, 7.5, 20), ("lunch", LUNCHES, 12.5, 25),
                                       ("dinner", DINNERS, 18.75, 25)):
            label, c, p, f = rnd.choice(pool)
            carbs_last = 0
            if slot == "breakfast" and d in (3, 4):
                label, c, p, f = "toast with jam", 48, 5, 2
            if slot == "breakfast" and d in (5, 6):
                label, c, p, f, carbs_last = "eggs and greens first, then toast", 48, 18, 4, 1
            minutes = int(hh * 60 + rnd.uniform(-mm_jit, mm_jit))
            ts = datetime.combine(day_date[d], datetime.min.time()) + timedelta(minutes=minutes)
            meals.append({"ts": _iso(ts), "label": label, "carbs_g": c + rnd.randint(-4, 4),
                          "protein_g": p, "fiber_g": f, "carbs_last": carbs_last, "source": "voice", "notes": slot})
        if d in (10, 15):
            ts = datetime.combine(day_date[d], datetime.min.time()) + timedelta(hours=15, minutes=30)
            meals.append({"ts": _iso(ts), "label": "crackers and juice", "carbs_g": 28, "protein_g": 3,
                          "fiber_g": 1, "carbs_last": 0, "source": "voice", "notes": "snack"})
    meals.sort(key=lambda m: m["ts"])

    # ---------------- steroid + insulin logs ----------------
    steroid_doses, insulin_log = [], []
    for d in range(1, sc.n_days + 1):
        mg = sc.steroid_mg(d)
        if mg:
            t = datetime.combine(day_date[d], datetime.min.time()) + timedelta(hours=8, minutes=rnd.randint(0, 12))
            steroid_doses.append({"ts": _iso(t), "drug": "prednisone", "route": "oral", "dose_mg": mg, "source": "manual"})
        t = datetime.combine(day_date[d], datetime.min.time()) + timedelta(hours=21, minutes=30 + rnd.randint(-8, 10))
        note = "dose raised after clinic call about high mornings" if d == 16 else None
        insulin_log.append({"ts": _iso(t), "units": sc.units(d), "insulin": "insulin glargine", "source": "voice",
                            "confirmed": 1, "steps_checked": 1 if d >= 20 else None, "note": note})

    # ---------------- injection sites: good rotation, then the lower right of the belly 7 of the last 9 nights ----------------
    clock = ["belly-upper-right", "belly-lower-right", "belly-lower-left", "belly-upper-left"]
    injection_sites = [{"ts": r["ts"], "zone": clock[d % 4] if d < 21 else ("belly-lower-left" if d in (24, 27) else "belly-lower-right"),
                        "source": "voice"} for d, r in enumerate(insulin_log)]

    # ---------------- glucose model ----------------
    dose_times = [(datetime.fromisoformat(r["ts"]), d + 1) for d, r in enumerate(insulin_log)]  # (time, day)
    steroid_times = [(datetime.fromisoformat(r["ts"]), r["dose_mg"]) for r in steroid_doses]
    meal_objs = []
    for m in meals:
        tm = datetime.fromisoformat(m["ts"])
        dd = (tm.date() - first).days + 1
        dinner = m["notes"] == "dinner"
        walked = dinner and wear_by_date[tm.date().isoformat()]["walk_after_dinner_min"] >= 10
        meal_objs.append((tm, m, walked))

    def steroid_factor(t: datetime) -> float:
        return sum(_steroid_curve((t - t0).total_seconds() / 3600, mg) for t0, mg in steroid_times)

    def recent_steroid_mg(t: datetime) -> float:
        best = 0.0
        for t0, mg in steroid_times:
            if 0 <= (t - t0).total_seconds() <= 24 * 3600:
                best = max(best, mg)
        return best

    def basal_units_eff(t: datetime) -> float:
        last_day, last_t = 0, None
        for dt_, dday in dose_times:
            if dt_ <= t:
                last_t, last_day = dt_, dday
            else:
                break
        if last_t is None:                                  # before the first logged dose: assume usual dose delivered
            return 18.0
        return sc.units(last_day) if sc.delivered(last_day) else 0.0

    start_t = datetime.combine(day_date[1], datetime.min.time())
    n_steps = sc.n_days * 96
    ar, glucose = 0.0, []
    for i in range(n_steps):
        t = start_t + timedelta(minutes=15 * i)
        h = t.hour + t.minute / 60
        units_eff = basal_units_eff(t)
        g = 175.0 - 3.5 * units_eff
        g += 0.45 * recent_steroid_mg(t)                                   # modest steroid baseline lift
        g += 15.0 * _bell(h, 6.0, 1.3)                                      # dawn rise
        g -= 4.5 * max(0.0, units_eff - 18.0) * _bell(h, 3.5, 1.6)          # nocturnal dip with higher basal dose
        d_idx = (t.date() - first).days + 1
        prev_wear = wear_by_date.get(t.date().isoformat())
        if prev_wear and prev_wear["sleep_quality"] < 60:                   # poor night -> higher morning
            g += 10.0 / (1 + math.exp(-(h - 4))) / (1 + math.exp(h - 12))
        s_now = steroid_factor(t)
        g += 38.0 * s_now                                                   # afternoon steroid bump
        for tm, m, walked in meal_objs:
            hrs = (t - tm).total_seconds() / 3600
            if hrs < 0 or hrs > 6:
                continue
            amp = max(0.0, 1.05 * m["carbs_g"] - 0.30 * m["protein_g"] - 1.5 * m["fiber_g"])
            if m["carbs_last"]:
                amp *= 0.62
            if walked:
                amp *= 0.68
            amp *= 1 + 1.1 * steroid_factor(tm + timedelta(minutes=90))
            x = hrs / 1.1
            g += amp * x * math.exp(1 - x)
        ar = 0.92 * ar + rnd.gauss(0, 1.6)
        g += ar
        glucose.append([t, g])

    # compression-low artifact: night of day 27 -> early morning of day 28 (V-shaped, ~45 min)
    art_day = min(28, sc.n_days)
    art_start = datetime.combine(day_date[art_day], datetime.min.time()) + timedelta(hours=2, minutes=45)
    for k, drop in enumerate([0, 25, 50, 52, 45, 20, 0]):
        idx = int((art_start - start_t).total_seconds() // 900) + k
        glucose[idx][1] -= drop

    gaps = [(5, 2.0, 4.5), (18, 14.0, 15.25), (29, 8.0, 8.75)]            # (day, from hour, to hour) missing readings
    skip = set()
    for gd, a, b in gaps:
        if gd <= sc.n_days:
            base = datetime.combine(day_date[gd], datetime.min.time())
            for hh in [a + 0.25 * j for j in range(int((b - a) / 0.25) + 1)]:
                skip.add(_iso(base + timedelta(hours=hh)))
    glucose_rows = [{"ts": _iso(t), "mgdl": float(round(max(40.0, min(400.0, g)))), "source": "libre"}
                    for t, g in glucose if _iso(t) not in skip]

    # ---------------- medications ----------------
    meds = [
        {"name": "Metformin", "drug_class": "biguanide", "dose": "1000 mg", "route": "oral", "schedule": "twice daily with meals",
         "start": "2021-03-01", "end": None, "notes": None},
        {"name": "Semaglutide", "drug_class": "GLP-1 receptor agonist", "dose": "1 mg", "route": "subcutaneous injection",
         "schedule": "once weekly (Sundays)", "start": "2024-01-07", "end": None, "notes": "weekly injection"},
        {"name": "Atorvastatin", "drug_class": "statin", "dose": "20 mg", "route": "oral", "schedule": "nightly",
         "start": "2020-05-10", "end": None, "notes": None},
        {"name": "Insulin glargine", "drug_class": "basal insulin", "dose": "18 units", "route": "subcutaneous pen",
         "schedule": "bedtime", "start": (first - timedelta(days=60)).isoformat(), "end": dstr(15), "notes": None},
        {"name": "Insulin glargine", "drug_class": "basal insulin", "dose": "26 units", "route": "subcutaneous pen",
         "schedule": "bedtime", "start": dstr(16), "end": dstr(24),
         "notes": "increased by clinic for high morning glucose"},
        {"name": "Insulin glargine", "drug_class": "basal insulin", "dose": "20 units", "route": "subcutaneous pen",
         "schedule": "bedtime", "start": dstr(25), "end": None, "notes": "reduced after overnight lows"},
        {"name": "Prednisone taper", "drug_class": "glucocorticoid", "dose": "30 mg x5d, 20 mg x5d, 10 mg x5d", "route": "oral",
         "schedule": "once daily in the morning", "start": dstr(9), "end": dstr(23),
         "notes": "short course for an inflammatory flare"},
    ]

    journal = [
        (10, "How did you sleep?", "Barely slept. The steroid has me wired at night."),
        (13, "Anything unusual today?", "Morning number was high again, in the 190s. I took my night insulin like always."),
        (17, "Anything to tell the clinic?", "They raised my night insulin but mornings are still high. Afternoons are worse on the pills."),
        (20, "Anything unusual today?", "Realized part of my pen routine was wrong. I am going through the check out loud from now on."),
        (23, "Any symptoms overnight?", "Woke up shaky around 3 in the morning and had some juice."),
        (28, "Any symptoms overnight?", "Sensor alarmed around 3 but I felt fine. I had been lying on my arm."),
    ]
    journal_rows = [{"ts": _iso(datetime.combine(day_date[d], datetime.min.time()) + timedelta(hours=20, minutes=15)),
                     "prompt": p, "body": b} for d, p, b in journal]

    truth = {
        "scenario": {"failure_days": sc.failure_days, "seed": sc.seed, "n_days": sc.n_days},
        "undelivered_dose_dates": [dstr(d) for d in range(sc.failure_days[0], sc.failure_days[1] + 1)] if sc.failure_days else [],
        "affected_mornings": [dstr(d) for d in range(sc.failure_days[0] + 1, sc.failure_days[1] + 2)] if sc.failure_days else [],
        "steroid_course": [{"from": dstr(a), "to": dstr(b), "mg": mg} for a, b, mg in sc.steroid_course],
        "dose_raised_on": dstr(16),
        "delivery_restored_dose_date": dstr(sc.failure_days[1] + 1) if sc.failure_days else None,
        "compression_artifact_morning": dstr(art_day),
        "note": "Toy glucose model; not physiologically validated.",
    }
    return {
        "today": today, "first_day": first, "glucose": glucose_rows, "medications": meds,
        "steroid_doses": steroid_doses, "insulin_log": insulin_log, "meals": meals,
        "wearable_daily": wearable, "profile": dict(PROFILE), "journal": journal_rows, "truth": truth,
        "injection_sites": injection_sites,
        "identity": {"name": [f"{PATIENT['given']} {PATIENT['family']}", PATIENT["given"], PATIENT["family"]],
                     "dob": [PATIENT["dob"]], "mrn": [PATIENT["mrn"]], "phone": [PATIENT["phone"]],
                     "email": [PATIENT["email"]]},
    }


def load_into(conn, data: dict) -> dict[str, int]:
    from . import db

    c = conn
    c.executemany("INSERT OR REPLACE INTO glucose(ts,mgdl,source) VALUES (:ts,:mgdl,:source)", data["glucose"])
    c.executemany("""INSERT INTO medications(name,drug_class,dose,route,schedule,start,end,notes)
                     VALUES (:name,:drug_class,:dose,:route,:schedule,:start,:end,:notes)""", data["medications"])
    c.executemany("INSERT INTO steroid_doses(ts,drug,route,dose_mg,source) VALUES (:ts,:drug,:route,:dose_mg,:source)",
                  data["steroid_doses"])
    c.executemany("""INSERT INTO insulin_log(ts,units,insulin,source,confirmed,steps_checked,note)
                     VALUES (:ts,:units,:insulin,:source,:confirmed,:steps_checked,:note)""", data["insulin_log"])
    c.executemany("""INSERT INTO meals(ts,label,carbs_g,protein_g,fiber_g,carbs_last,source,notes)
                     VALUES (:ts,:label,:carbs_g,:protein_g,:fiber_g,:carbs_last,:source,:notes)""", data["meals"])
    c.executemany("""INSERT OR REPLACE INTO wearable_daily(date,sleep_h,sleep_quality,steps,active_min,resting_hr,walk_after_dinner_min)
                     VALUES (:date,:sleep_h,:sleep_quality,:steps,:active_min,:resting_hr,:walk_after_dinner_min)""",
                  data["wearable_daily"])
    c.executemany("INSERT OR REPLACE INTO profile(key,value) VALUES (?,?)", list(data["profile"].items()))
    c.executemany("INSERT INTO journal(ts,prompt,body) VALUES (:ts,:prompt,:body)", data["journal"])
    c.executemany("INSERT INTO injection_sites(ts,zone,source) VALUES (:ts,:zone,:source)", data["injection_sites"])
    c.commit()
    db.save_identity(c, data["identity"])
    return {k: len(data[k]) for k in ("glucose", "medications", "steroid_doses", "insulin_log", "meals",
                                      "wearable_daily", "journal", "injection_sites")}


def write_truth(path: Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data["truth"], indent=2))
