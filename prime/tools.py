"""Tools the agent can call. All run LOCALLY against SQLite; the model only ever sees their (redacted) results.

Citation ids (verified by the app; unknown ids are shown to the user as 'unverified'):
  day:YYYY-MM-DD  glucose summary for a day     ins:N   insulin log entry     meal:N  meal entry
  rx:N            medication row                ste:N   steroid dose          j:N     journal entry
  site:N          injection site entry          src:xxxxxxxx    evidence passage
"""
from __future__ import annotations

import json
import re
import sqlite3
import statistics as st
from datetime import date, datetime, timedelta
from pathlib import Path

from . import analysis as A
from . import evidence as E
from . import pens as PENS
from . import sites as SITES
from .calendar import write_ics

DOSE_SANITY_RATIO = 1.5          # warn when a logged dose is >= 150% of the recent median
MAX_POINTS = 200


def _d(s: str) -> str:
    return s[:10]


class Toolbox:
    def __init__(self, conn: sqlite3.Connection, ics_path: Path, now: datetime | None = None):
        self.conn = conn
        self.ics_path = ics_path
        self._now = now

    def now(self) -> datetime:
        return self._now or datetime.now()

    @property
    def today(self) -> date:
        return self.now().date()

    # ------------------------------------------------------------------ glucose
    def get_glucose(self, start: str, end: str, mode: str = "summary") -> dict:
        pts = A.read_glucose(self.conn, start, end)
        if not pts:
            return {"found": False, "note": "No glucose readings in that range."}
        out = {"found": True, "range": [start, end], "summary": A.summarize(pts), "gaps": A.gaps(pts)[:10]}
        days = sorted({t.date().isoformat() for t, _ in pts})
        out["day_cites"] = [f"day:{x}" for x in days[:14]]
        if mode == "points":
            if len(pts) > MAX_POINTS:
                return {"error": f"{len(pts)} points is too many; use mode 'hourly' or 'daily', or a shorter range (max {MAX_POINTS})."}
            out["points"] = [[t.isoformat(timespec="minutes"), g] for t, g in pts]
        elif mode == "hourly":
            h = A.hourly(pts)
            if len(h) > 96:
                return {"error": "Too many hours; use mode 'daily' or a range of 4 days or less."}
            out["hourly"] = h
        elif mode == "daily":
            out["daily"] = []
            for x in days:
                f = A.day_features(self.conn, date.fromisoformat(x))
                if f:
                    out["daily"].append({k: f[k] for k in ("date", "cite", "fasting", "afternoon_mean", "mean", "tir", "min", "max",
                                                          "steroid_mg_today", "units_prev_night")})
        elif mode != "summary":
            return {"error": "mode must be summary, hourly, daily or points"}
        return out

    # ------------------------------------------------------------------ medications, insulin, meals, wearables
    def get_medications(self, date: str) -> dict:  # noqa: A002 - argument name is part of the contract
        dd = _d(date)
        rows = self.conn.execute("SELECT * FROM medications WHERE start <= ? AND (end IS NULL OR end >= ?) ORDER BY name, start",
                                 (dd, dd)).fetchall()
        meds = [{"cite": f"rx:{r['id']}", "name": r["name"], "class": r["drug_class"], "dose": r["dose"], "route": r["route"],
                 "schedule": r["schedule"], "started": r["start"], "notes": r["notes"]} for r in rows]
        doses = self.conn.execute("SELECT * FROM steroid_doses WHERE substr(ts,1,10)=? ORDER BY ts", (dd,)).fetchall()
        course = self.conn.execute("SELECT MIN(substr(ts,1,10)) a, MAX(substr(ts,1,10)) b, COUNT(*) n FROM steroid_doses").fetchone()
        steroid = {"active_today": bool(doses), "doses_today": [{"cite": f"ste:{r['id']}", "ts": r["ts"], "drug": r["drug"], "mg": r["dose_mg"]}
                                                                 for r in doses]}
        if course["n"]:
            steroid["course"] = {"first_dose": course["a"], "last_dose": course["b"], "doses": course["n"]}
            if doses:
                steroid["course_day"] = (date_cls(dd) - date_cls(course["a"])).days + 1
        return {"date": dd, "active_medications": meds, "steroid": steroid}

    def get_insulin_log(self, date: str, end_date: str | None = None) -> dict:  # noqa: A002
        a, b = _d(date), _d(end_date or date)
        rows = self.conn.execute("SELECT * FROM insulin_log WHERE substr(ts,1,10) BETWEEN ? AND ? ORDER BY ts", (a, b)).fetchall()
        return {"range": [a, b], "entries": [{"cite": f"ins:{r['id']}", "ts": r["ts"], "units": r["units"], "insulin": r["insulin"],
                                              "source": r["source"], "confirmed_by_readback": bool(r["confirmed"]),
                                              "pre_injection_check_done": None if r["steps_checked"] is None else bool(r["steps_checked"]),
                                              "note": r["note"]} for r in rows],
                "note": "A bedtime dose affects the next morning's glucose."}

    def get_meals(self, date: str, end_date: str | None = None) -> dict:  # noqa: A002
        a, b = _d(date), _d(end_date or date)
        rows = self.conn.execute("SELECT * FROM meals WHERE substr(ts,1,10) BETWEEN ? AND ? ORDER BY ts", (a, b)).fetchall()
        return {"range": [a, b], "meals": [{"cite": f"meal:{r['id']}", "ts": r["ts"], "label": r["label"], "carbs_g": r["carbs_g"],
                                            "protein_g": r["protein_g"], "fiber_g": r["fiber_g"],
                                            "vegetables_protein_first": bool(r["carbs_last"]), "kind": r["notes"]} for r in rows]}

    def get_wearable_summary(self, date: str) -> dict:  # noqa: A002
        dd = _d(date)
        r = self.conn.execute("SELECT * FROM wearable_daily WHERE date=?", (dd,)).fetchone()
        if not r:
            return {"found": False, "date": dd}
        return {"found": True, "date": dd, "cite": f"day:{dd}", "sleep_hours_last_night": r["sleep_h"], "sleep_quality_0_100": r["sleep_quality"],
                "steps": r["steps"], "active_minutes": r["active_min"], "resting_hr": r["resting_hr"],
                "walk_after_dinner_minutes": r["walk_after_dinner_min"]}

    # ------------------------------------------------------------------ evidence
    def search_medical_evidence(self, question: str, k: int = 4) -> dict:
        res = E.search_evidence(self.conn, question, k=max(1, min(int(k), 8)))
        return {"passages": res, "note": "Summaries of cited sources. Weigh each by evidence_level; do not present consumer or news items as guidelines."}

    # ------------------------------------------------------------------ analysis
    def get_episode_context(self, ts: str, window_h: float = 6) -> dict:
        t = datetime.fromisoformat(ts if "T" in ts else ts + "T12:00:00")
        w = max(1.0, min(float(window_h), 12.0))
        a, b = t - timedelta(hours=w), t + timedelta(hours=2)
        pts = A.read_glucose(self.conn, a.isoformat(timespec="seconds"), b.isoformat(timespec="seconds"))
        trace = [[x.isoformat(timespec="minutes"), g] for x, g in pts[::2]]               # every 30 min
        meals = self.conn.execute("SELECT * FROM meals WHERE ts BETWEEN ? AND ? ORDER BY ts",
                                  (a.isoformat(timespec="seconds"), t.isoformat(timespec="seconds"))).fetchall()
        ins = self.conn.execute("SELECT * FROM insulin_log WHERE ts BETWEEN ? AND ? ORDER BY ts",
                                ((t - timedelta(hours=36)).isoformat(timespec="seconds"), t.isoformat(timespec="seconds"))).fetchall()
        ste = self.conn.execute("SELECT * FROM steroid_doses WHERE ts BETWEEN ? AND ? ORDER BY ts",
                                ((t - timedelta(hours=30)).isoformat(timespec="seconds"), t.isoformat(timespec="seconds"))).fetchall()
        exc = [A.annotate(self.conn, x) for x in A.excursions(pts)]
        return {
            "at": t.isoformat(timespec="minutes"), "window_hours_before": w, "day_cite": f"day:{t.date().isoformat()}",
            "glucose_30min": trace, "glucose_summary": A.summarize(pts),
            "meals_in_window": [{"cite": f"meal:{r['id']}", "ts": r["ts"], "label": r["label"], "carbs_g": r["carbs_g"], "protein_g": r["protein_g"],
                                 "minutes_before": int((t - datetime.fromisoformat(r["ts"])).total_seconds() / 60)} for r in meals],
            "insulin_last_36h": [{"cite": f"ins:{r['id']}", "ts": r["ts"], "units": r["units"],
                                  "pre_injection_check_done": None if r["steps_checked"] is None else bool(r["steps_checked"])} for r in ins],
            "steroid_last_30h": [{"cite": f"ste:{r['id']}", "ts": r["ts"], "mg": r["dose_mg"], "drug": r["drug"],
                                  "hours_before": round((t - datetime.fromisoformat(r["ts"])).total_seconds() / 3600, 1)} for r in ste],
            "wearable_today": self.get_wearable_summary(t.date().isoformat()),
            "wearable_yesterday": self.get_wearable_summary((t.date() - timedelta(days=1)).isoformat()),
            "excursions_in_window": exc,
        }

    def find_excursions(self, start: str, end: str, kinds: str = "both") -> dict:
        pts = A.read_glucose(self.conn, start, end)
        ex = [A.annotate(self.conn, x) for x in A.excursions(pts)]
        if kinds in ("high", "low"):
            ex = [x for x in ex if x["kind"] == kinds]
        return {"range": [start, end], "count": len(ex), "excursions": ex[:40],
                "note": "Lows flagged possible_compression_artifact have a steep drop and recovery; confirm with a fingerstick before treating."}

    def check_dose_response(self, start: str, end: str) -> dict:
        return A.check_dose_response(self.conn, start, end)

    def visit_summary(self, start: str, end: str) -> dict:
        pts = A.read_glucose(self.conn, start, end)
        ex = [A.annotate(self.conn, x) for x in A.excursions(pts)]
        dr = A.check_dose_response(self.conn, start, end)
        ins = self.conn.execute("SELECT substr(ts,1,10) d, units FROM insulin_log WHERE substr(ts,1,10) BETWEEN ? AND ? ORDER BY ts",
                                (_d(start), _d(end))).fetchall()
        dose_changes, prev = [], None
        for r in ins:
            if prev is not None and r["units"] != prev:
                dose_changes.append({"date": r["d"], "from_units": prev, "to_units": r["units"]})
            prev = r["units"]
        steroid = [dict(r) for r in self.conn.execute(
            "SELECT substr(ts,1,10) d, drug, dose_mg FROM steroid_doses WHERE substr(ts,1,10) BETWEEN ? AND ? ORDER BY ts", (_d(start), _d(end)))]
        lows = [x for x in ex if x["kind"] == "low"]
        return {
            "range": [_d(start), _d(end)], "glucose_summary": A.summarize(pts),
            "targets_note": "Consensus targets: >=70% time in range (70-180), <4% below 70, <1% below 54, <25% above 180, <5% above 250; personalized.",
            "high_episodes": sum(1 for x in ex if x["kind"] == "high"),
            "lows": [{"start": x["start"], "level": x["level"], "nadir": x["peak_or_nadir"], "duration_min": x["duration_min"],
                      "possible_compression_artifact": x["possible_compression_artifact"], "day_cite": x["day_cite"],
                      "steroid_before": x["context"]["steroid_before"], "last_insulin": x["context"]["last_insulin"]} for x in lows[:12]],
            "insulin_dose_changes": dose_changes,
            "steroid_days": steroid,
            "dose_response": {"flagged": dr.get("flagged"), "patterns": [
                {k: p[k] for k in ("from", "to", "days", "fasting_delta_mean", "logged_units_range", "dose_escalated",
                                   "escalation_without_response", "confidence", "recovered_on", "day_cites", "risk_note") if k in p}
                for p in dr.get("patterns", [])]},
            "meal_experiment": A.meal_experiment(self.conn, start, end),
            "questions_to_consider": [
                "Was the pen routine (both needle caps off, safety test, dose clicks) checked with someone while mornings were high?",
                "Should the bedtime dose and the steroid taper be reviewed together?",
                "Which of the overnight lows were real, and which looked like a sensor pressing against the arm?",
            ],
        }

    # ------------------------------------------------------------------ pen check
    def pre_injection_checklist(self, pen: str | None = None) -> dict:
        """The spoken pen check, following the person's own pen when it is known (pens.py; numbers cited per pen)."""
        def c(fragment):
            r = E.get_by_title(self.conn, fragment)
            return r["cite"] if r else None
        p = PENS.get(pen or self.get_pen())
        steps = PENS.steps(p, c, c(PENS.title(p)) if p else None)
        if p and p["family"] == "glp1":
            return {"steps": steps, "teach_back_questions": [
                        "Which cap do you take off, and when?", "How do you know the injection is finished?", "Where do you put the used needle or pen?"],
                    "reminder": "Follow the instructions for your own pen, and ask your pharmacist or care team to watch you do it once.",
                    "pen": {"id": p["id"], "name": p["name"], "hold_seconds": PENS.hold_seconds(p), "release": PENS.release(p), "family": "glp1"}}
        return {"steps": steps, "teach_back_questions": [
            "How many caps are on the needle, and which one do you keep?",
            "What should happen at the needle tip during the safety test?",
            "How many seconds do you count before pulling the needle out?"],
            "reminder": "Pens differ. Follow the instructions for your own pen and ask your pharmacist or care team to watch you do it once.",
            "pen": {"id": p["id"], "name": p["name"], "hold_seconds": PENS.hold_seconds(p), "release": PENS.release(p), "family": "insulin"} if p else None}

    def get_pen(self) -> str | None:
        r = self.conn.execute("SELECT value FROM profile WHERE key='pen'").fetchone()
        return r["value"] if r and PENS.get(r["value"]) else None

    def set_insulin_pen(self, pen: str | None) -> dict:
        if pen and not PENS.get(pen):
            return {"saved": False, "error": "Unknown pen. Use one of: " + ", ".join(PENS.BY_ID)}
        if pen:
            self.conn.execute("INSERT OR REPLACE INTO profile(key,value) VALUES ('pen',?)", (pen,))
        else:
            self.conn.execute("DELETE FROM profile WHERE key='pen'")
        self.conn.commit()
        return {"saved": True, "readback": f"Your pen is now {PENS.get(pen)['name']}." if pen else "I'll use the general pen steps."}

    def get_injection_sites(self, limit: int = 10) -> dict:
        """The last injections' sites, the next spot in the rotation, and an overuse warning. All decided in code.
        Rotation depends on the order of injections, not the calendar, so this reads the last `limit` entries."""
        rows = self.conn.execute("SELECT * FROM injection_sites ORDER BY ts DESC LIMIT ?", (max(7, min(int(limit), 30)),)).fetchall()
        history = [r["zone"] for r in rows]
        nxt = SITES.suggest(history)
        src = lambda t: (E.get_by_title(self.conn, t) or {}).get("cite")          # noqa: E731
        out = {"recent": [{"cite": f"site:{r['id']}", "ts": r["ts"], "zone": r["zone"], "where": SITES.ZONES.get(r["zone"], r["zone"])}
                          for r in rows],
               "suggested_next": {"zone": nxt, "where": SITES.ZONES[nxt],
                                  "why": "the spot in this area used longest ago" if history else "a starting point; any spot in this area works"},
               "checks": [{"say": s, "src": src(t)} for s, t in SITES.CHECKS],
               "overuse": None}
        if (o := SITES.overuse(history)):
            out["overuse"] = o | {"say": f"You used {o['where']} for {o['count']} of your last {o['of']} injections. Using the same spot "
                                         "can cause lumps that change how insulin is absorbed. Feel that area for firm or lumpy skin, and if "
                                         "you find any, avoid it and tell your care team.",
                                  "src": src("Lumps from injecting in the same spot")}
        return out

    def log_injection_site(self, zone: str, ts: str | None = None) -> dict:
        if zone not in SITES.ZONES:
            return {"logged": False, "error": f"Unknown site. Use one of: {', '.join(SITES.ZONES)}."}
        when = datetime.fromisoformat(ts) if ts else self.now()
        cur = self.conn.execute("INSERT INTO injection_sites(ts,zone,source) VALUES (?,?,?)",
                                (when.isoformat(timespec="seconds"), zone, "voice"))
        self.conn.commit()
        return {"logged": True, "cite": f"site:{cur.lastrowid}", "readback": f"Noted {SITES.ZONES[zone]} for this injection."}

    # ------------------------------------------------------------------ writes (voice logging)
    def log_insulin(self, units: float, insulin: str = "insulin glargine", ts: str | None = None,
                    pre_injection_check_done: bool | None = None, note: str | None = None) -> dict:
        units = float(units)
        if not (0 < units <= 100):
            return {"logged": False, "error": "Units must be between 0 and 100. Please repeat the dose."}
        recent = [r["units"] for r in self.conn.execute(
            "SELECT units FROM insulin_log WHERE insulin=? ORDER BY ts DESC LIMIT 7", (insulin,))]
        warning = None
        if recent:
            med = st.median(recent)
            if units >= DOSE_SANITY_RATIO * med:
                warning = (f"STOP. {units:g} units is much higher than your recent doses (usually about {med:g}). "
                           "Do not inject until you have confirmed this dose with your care team or pharmacist.")
        when = datetime.fromisoformat(ts) if ts else self.now()
        cur = self.conn.execute(
            "INSERT INTO insulin_log(ts,units,insulin,source,confirmed,steps_checked,note) VALUES (?,?,?,?,?,?,?)",
            (when.isoformat(timespec="seconds"), units, insulin, "voice", 1,
             None if pre_injection_check_done is None else int(pre_injection_check_done), note))
        self.conn.commit()
        out = {"logged": True, "cite": f"ins:{cur.lastrowid}",
               "readback": f"Logged {units:g} units of {insulin} at {when.strftime('%I:%M %p').lstrip('0')}."}
        if warning:
            out["warning"] = warning
        return out

    def log_meal(self, label: str, ts: str | None = None, carbs_g: float | None = None, protein_g: float | None = None,
                 fiber_g: float | None = None, vegetables_protein_first: bool = False) -> dict:
        when = datetime.fromisoformat(ts) if ts else self.now()
        cur = self.conn.execute(
            "INSERT INTO meals(ts,label,carbs_g,protein_g,fiber_g,carbs_last,source,notes) VALUES (?,?,?,?,?,?,?,?)",
            (when.isoformat(timespec="seconds"), label, carbs_g, protein_g, fiber_g, int(vegetables_protein_first), "voice", "logged"))
        self.conn.commit()
        return {"logged": True, "cite": f"meal:{cur.lastrowid}", "readback": f"Logged {label} at {when.strftime('%I:%M %p').lstrip('0')}."}

    def add_journal(self, body: str, prompt: str | None = None) -> dict:
        cur = self.conn.execute("INSERT INTO journal(ts,prompt,body) VALUES (?,?,?)",
                                (self.now().isoformat(timespec="seconds"), prompt, body))
        self.conn.commit()
        return {"saved": True, "cite": f"j:{cur.lastrowid}"}

    def search_journal(self, query: str, limit: int = 5) -> dict:
        tokens = re.findall(r"[A-Za-z0-9]{3,}", query)
        rows = []
        if tokens:
            match = " OR ".join(f'"{t}"' for t in tokens)
            rows = self.conn.execute("""SELECT j.* FROM journal_fts f JOIN journal j ON j.id=f.rowid
                                        WHERE journal_fts MATCH ? ORDER BY rank LIMIT ?""", (match, limit)).fetchall()
        return {"entries": [{"cite": f"j:{r['id']}", "date": r["ts"][:10], "prompt": r["prompt"], "text": r["body"]} for r in rows]}

    def create_reminder(self, title: str, due: str, repeat: str | None = None, notes: str | None = None, kind: str = "general") -> dict:
        datetime.fromisoformat(due)
        if repeat not in (None, "daily", "weekly", "monthly"):
            raise ValueError("repeat must be daily, weekly, monthly or null")
        cur = self.conn.execute("INSERT INTO reminders(title,due,repeat,notes,kind,created) VALUES (?,?,?,?,?,?)",
                                (title, due, repeat, notes, kind, self.now().isoformat(timespec="seconds")))
        self.conn.commit()
        n = write_ics(self.conn, self.ics_path)
        return {"saved": True, "reminder_id": cur.lastrowid, "calendar_file": str(self.ics_path), "total_reminders": n}

    def list_reminders(self) -> dict:
        rows = self.conn.execute("SELECT * FROM reminders ORDER BY due").fetchall()
        return {"reminders": [dict(r) for r in rows]}

    # ------------------------------------------------------------------ dispatch
    def dispatch(self, name: str, args: dict) -> str:
        fn = getattr(self, name, None)
        if name not in TOOL_NAMES or fn is None:
            return json.dumps({"error": f"unknown tool {name}"})
        try:
            return json.dumps(fn(**args), default=str, ensure_ascii=False)
        except Exception as e:                       # surface errors so the model can recover
            return json.dumps({"error": f"{type(e).__name__}: {e}"})


def date_cls(s: str) -> date:
    return date.fromisoformat(s)


def _fn(name, desc, props, required=()):
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": list(required)}}}


_DT = {"type": "string", "description": "ISO date (2026-10-01) or datetime (2026-10-01T14:30:00)"}
TOOL_SCHEMAS = [
    _fn("get_glucose", "CGM readings for a range. mode: summary (default), hourly (<=4 days), daily, or points (<=200).",
        {"start": _DT, "end": _DT, "mode": {"type": "string", "enum": ["summary", "hourly", "daily", "points"]}}, ["start", "end"]),
    _fn("get_medications", "Active medications on a date, plus steroid dosing status (course day, doses that day).",
        {"date": _DT}, ["date"]),
    _fn("get_insulin_log", "Insulin doses logged on a date (or range). A bedtime dose affects the next morning.",
        {"date": _DT, "end_date": _DT}, ["date"]),
    _fn("get_meals", "Meals logged on a date (or range), with carbs/protein/fiber and whether vegetables/protein were eaten first.",
        {"date": _DT, "end_date": _DT}, ["date"]),
    _fn("get_wearable_summary", "Sleep, steps, activity, resting heart rate and post-dinner walk for a date.", {"date": _DT}, ["date"]),
    _fn("search_medical_evidence", "Search the curated evidence library (steroids, dawn phenomenon, GLP-1, meal order, sleep, CGM artifacts, "
        "insulin pen technique, low-vision accessibility). Cite results by their src id.",
        {"question": {"type": "string"}, "k": {"type": "integer"}}, ["question"]),
    _fn("get_episode_context", "Everything around one moment: glucose trace, meals, insulin, steroid doses, sleep, and excursions. "
        "Use for 'why was I high/low at X?'.", {"ts": _DT, "window_h": {"type": "number"}}, ["ts"]),
    _fn("find_excursions", "Highs (>180) and lows (<70) in a range, with context and a compression-artifact flag for lows.",
        {"start": _DT, "end": _DT, "kinds": {"type": "string", "enum": ["both", "high", "low"]}}, ["start", "end"]),
    _fn("check_dose_response", "Compares recent mornings with the person's OWN reference days given the logged insulin and steroid timing. "
        "Flags a pattern where logged insulin did not seem to have its usual effect, with competing hypotheses. CALL THIS when mornings are high "
        "despite logged insulin, or when asked whether insulin is working.", {"start": _DT, "end": _DT}, ["start", "end"]),
    _fn("visit_summary", "Everything for a clinic visit over a range: glucose summary, lows, dose changes, steroid days, dose-response flags, "
        "meal experiment, and questions to ask.", {"start": _DT, "end": _DT}, ["start", "end"]),
    _fn("pre_injection_checklist", "The spoken step-by-step pen check (two needle caps, safety test, click counting) with teach-back questions, "
        "following the person's saved pen (safety-test units, hold time, mixing, from that pen's instructions). "
        "Use when the user is about to inject, or asks how to use the pen.", {"pen": {"type": "string", "description": "pen id; omit to use the saved pen"}}),
    _fn("set_insulin_pen", "Save which insulin pen or GLP-1 pen the person uses, so the pen check follows it. Ids: " +
        "; ".join(f"{p['id']} = {p['name']}" for p in PENS.ALL) + ". Confirm the readback.",
        {"pen": {"type": "string", "enum": list(PENS.BY_ID) or ["none"]}}, ["pen"]),
    _fn("log_insulin", "Log an insulin dose by voice. Read the result's readback to the user. If the result has a warning, say it first and plainly.",
        {"units": {"type": "number"}, "insulin": {"type": "string"}, "ts": _DT, "pre_injection_check_done": {"type": "boolean"},
         "note": {"type": "string"}}, ["units"]),
    _fn("get_injection_sites", "Where recent injections went, the next spot in the person's rotation, fixed reminders (distance from the "
        "navel, spacing, skin check) and an overuse warning. Use for 'where should I inject?' and before guiding an injection.",
        {"limit": {"type": "integer", "description": "how many recent injections to read (default 10)"}}),
    _fn("log_injection_site", "Record where an injection went. zone is one of: " + ", ".join(SITES.ZONES) + ". Read the readback.",
        {"zone": {"type": "string", "enum": list(SITES.ZONES)}, "ts": _DT}, ["zone"]),
    _fn("log_meal", "Log a meal by voice.", {"label": {"type": "string"}, "ts": _DT, "carbs_g": {"type": "number"}, "protein_g": {"type": "number"},
                                             "fiber_g": {"type": "number"}, "vegetables_protein_first": {"type": "boolean"}}, ["label"]),
    _fn("add_journal", "Save a note or symptom to the private journal.", {"body": {"type": "string"}, "prompt": {"type": "string"}}, ["body"]),
    _fn("search_journal", "Search the private journal for a symptom or topic.", {"query": {"type": "string"}, "limit": {"type": "integer"}}, ["query"]),
    _fn("create_reminder", "Create a calendar reminder (exported to a local .ics file).",
        {"title": {"type": "string"}, "due": {"type": "string", "description": "ISO datetime"}, "repeat": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
         "notes": {"type": "string"}, "kind": {"type": "string", "enum": ["medication", "lab", "appointment", "general"]}}, ["title", "due"]),
    _fn("list_reminders", "List reminders.", {}),
]
TOOL_NAMES = {s["function"]["name"] for s in TOOL_SCHEMAS}
