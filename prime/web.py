"""Hosted demo + local web UI.

Demo mode serves ONLY the synthetic patient. Each visitor gets a private copy of the database
(cookie-scoped), so journal entries, logged doses and reminders never leak between visitors. The API key
stays server-side; per-session and daily call caps protect the credit budget.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from . import analysis as A
from . import cgm, cgm_vision, cites, db, evidence, pens, speech, synthetic, vision, visit_note
from .cgm_data import CHECKS as CGM_CHECKS
from .sites import ZONES
from .agent import EMERGENCY, EMERGENCY_REPLY, Agent
from .calendar import write_ics
from .config import Settings, load_settings
from .llm import LLM
from .privacy import Redactor
from .tools import Toolbox

STATIC = Path(__file__).parent / "static"
PLACEHOLDER = re.compile(r"\[(PATIENT|DOB|MRN|PHONE|EMAIL|SSN)\]")


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class FramesIn(BaseModel):
    check: str = Field(pattern="^(" + "|".join(vision.CHECKS) + ")$")
    frames: list[str] = Field(min_length=1, max_length=vision.MAX_FRAMES)

    @field_validator("frames")
    @classmethod
    def _images(cls, v):
        for u in v:
            if not re.match(r"^data:image/(jpeg|png|webp);base64,", u) or len(u) > 1_500_000:
                raise ValueError("frames must be JPEG, PNG or WebP data URLs under 1.5 MB")
        return v


class PenIn(BaseModel):
    pen: str | None = Field(default=None, max_length=60)


class CgmIn(BaseModel):
    cgm: str | None = Field(default=None, max_length=40)


class CgmFramesIn(FramesIn):                      # same frame rules as the pen check (JPEG/PNG/WebP data URLs under 1.5 MB), one to three frames
    check: str = Field(pattern="^(" + "|".join(CGM_CHECKS) + ")$")
    frames: list[str] = Field(min_length=1, max_length=3)


class SiteIn(BaseModel):
    zone: str = Field(pattern="^(" + "|".join(ZONES) + ")$")


class JournalIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    prompt: str | None = Field(default=None, max_length=300)


@dataclass
class Session:
    sid: str
    conn: object
    toolbox: Toolbox
    ics: Path
    history: list = field(default_factory=list)
    calls: int = 0
    speech: int = 0
    last_seen: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)
    agent: Agent | None = None


def build_template(root: Path, today: date | None = None) -> Path:
    path = root / "template.db"
    conn = db.connect(path)
    synthetic.load_into(conn, synthetic.build(today or date.today()))
    evidence.load_evidence(conn)
    conn.close()
    return path


class Sessions:
    def __init__(self, template: Path, root: Path, ttl: int = 6 * 3600, cap: int = 200):
        self.template, self.root, self.ttl, self.cap = template, root, ttl, cap
        self._s: dict[str, Session] = {}
        self._lock = threading.Lock()

    def _make(self, sid: str) -> Session:
        path = self.root / f"{sid}.db"
        shutil.copy(self.template, path)
        conn = db.connect(path, check_same_thread=False)
        ics = self.root / f"{sid}.ics"
        return Session(sid, conn, Toolbox(conn, ics), ics)

    def _drop(self, sid: str):
        s = self._s.pop(sid, None)
        if s:
            s.conn.close()
            for ext in (".db", ".ics"):
                (self.root / f"{sid}{ext}").unlink(missing_ok=True)

    def _evict(self):
        now = time.time()
        for sid, s in list(self._s.items()):
            if now - s.last_seen > self.ttl:
                self._drop(sid)
        while len(self._s) >= self.cap:
            self._drop(min(self._s, key=lambda k: self._s[k].last_seen))

    def get(self, sid: str | None) -> Session:
        with self._lock:
            if sid and sid in self._s:
                s = self._s[sid]
            else:
                self._evict()
                sid = uuid.uuid4().hex
                s = self._s[sid] = self._make(sid)
            s.last_seen = time.time()
            return s

    def reset(self, sid: str) -> Session:
        with self._lock:
            self._drop(sid)
            s = self._s[sid] = self._make(sid)
            return s


def create_app(settings: Settings | None = None, llm_factory=None, root: Path | None = None, today: date | None = None) -> FastAPI:
    settings = settings or load_settings()
    root = root or Path(tempfile.mkdtemp(prefix="prime-web-"))
    (root / "sessions").mkdir(parents=True, exist_ok=True)
    sessions = Sessions(build_template(root, today), root / "sessions")
    llm_factory = llm_factory or (lambda s, conn, red: LLM(s, conn, red))
    per_session = int(os.environ.get("DEMO_MAX_CALLS_PER_SESSION", "25"))
    per_day = int(os.environ.get("DEMO_MAX_CALLS_PER_DAY", "500"))
    speech_per_session = int(os.environ.get("DEMO_MAX_SPEECH_PER_SESSION", "60"))
    day = {"date": date.today(), "n": 0}
    day_lock = threading.Lock()

    app = FastAPI(title="Prime demo", docs_url=None, redoc_url=None)

    def sess(request: Request, response: Response) -> Session:
        s = sessions.get(request.cookies.get("prime_sid"))
        response.set_cookie("prime_sid", s.sid, max_age=6 * 3600, httponly=True, samesite="lax")
        return s

    # ---------------- pages ----------------
    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-cache"})   # a redeploy must not leave visitors on an old page


    @app.get("/health")
    @app.get("/api/health")
    def health():
        return {"ok": True, "model": settings.model, "key_configured": bool(settings.api_key), "speech": bool(settings.speech_model)}

    # ---------------- data for the left panel ----------------
    @app.get("/api/overview")
    def overview(request: Request, response: Response):
        s = sess(request, response)
        c = s.conn
        row = c.execute("SELECT MIN(substr(ts,1,10)) a, MAX(substr(ts,1,10)) b FROM glucose").fetchone()
        first, last = date.fromisoformat(row["a"]), date.fromisoformat(row["b"])
        days, d = [], first
        while d <= last:
            f = A.day_features(c, d)
            if f:
                days.append({k: f[k] for k in ("date", "cite", "fasting", "afternoon_mean", "mean", "tir", "min", "max", "units_prev_night",
                                              "steps_checked", "steroid_mg_today")})
            d += timedelta(days=1)
        dr = A.check_dose_response(c, first.isoformat(), last.isoformat())
        pattern = None
        if dr.get("patterns"):
            p = dr["patterns"][0]
            pattern = {k: p[k] for k in ("from", "to", "days", "fasting_delta_mean", "logged_units_range", "dose_escalated",
                                         "escalation_without_response", "confidence", "recovered_on", "reference_fasting", "reference_units")}
            pattern["risk_note"] = p.get("risk_note")
            pattern["safe_next_steps"] = dr["safe_next_steps"]
        lows = [A.annotate(c, x) for x in A.excursions(A.read_glucose(c, first.isoformat(), last.isoformat())) if x["kind"] == "low"]
        genuine = [x for x in lows if not x["possible_compression_artifact"]]
        deepest = min(genuine, key=lambda x: x["peak_or_nadir"]) if genuine else None
        artifact = next((x for x in lows if x["possible_compression_artifact"]), None)
        for d_ in days:
            d_["has_low"] = any(x["start"][:10] == d_["date"] for x in genuine)
            d_["has_artifact"] = bool(artifact and artifact["start"][:10] == d_["date"])
            d_["flagged_morning"] = bool(pattern and pattern["from"] <= d_["date"] <= pattern["to"])
        meds = s.toolbox.get_medications(last.isoformat())
        return {
            "first": first.isoformat(), "last": last.isoformat(), "days": days, "pattern": pattern,
            "highlights": {"deepest_low": deepest and {"date": deepest["start"][:10], "time": deepest["start"][11:], "nadir": deepest["peak_or_nadir"]},
                           "artifact": artifact and {"date": artifact["start"][:10], "time": artifact["start"][11:]}},
            "medications": meds["active_medications"], "profile": db.load_profile(c),
            "journal": [{"cite": f"j:{r['id']}", "date": r["ts"][:10], "text": r["body"]} for r in
                        c.execute("SELECT * FROM journal ORDER BY ts DESC LIMIT 8")],
            "reminders": [dict(r) for r in c.execute("SELECT * FROM reminders ORDER BY due")],
        }

    @app.get("/api/day")
    def day_view(request: Request, response: Response, date_: str = Query(alias="date")):
        s = sess(request, response)
        try:
            d = date.fromisoformat(date_)
        except ValueError:
            raise HTTPException(400, "date must be YYYY-MM-DD")
        c, ds = s.conn, d.isoformat()
        pts = A.read_glucose(c, ds, ds)
        if not pts:
            raise HTTPException(404, "No glucose data for that day")
        return {
            "date": ds, "cite": f"day:{ds}", "summary": A.summarize(pts),
            "points": [[t.strftime("%H:%M"), g] for t, g in pts],
            "meals": [{"cite": f"meal:{r['id']}", "t": r["ts"][11:16], "label": r["label"], "carbs_g": r["carbs_g"]}
                      for r in c.execute("SELECT * FROM meals WHERE substr(ts,1,10)=? ORDER BY ts", (ds,))],
            "insulin": [{"cite": f"ins:{r['id']}", "t": r["ts"][11:16], "units": r["units"], "check": r["steps_checked"]}
                        for r in c.execute("SELECT * FROM insulin_log WHERE substr(ts,1,10)=? ORDER BY ts", (ds,))],
            "steroid": [{"cite": f"ste:{r['id']}", "t": r["ts"][11:16], "mg": r["dose_mg"]}
                        for r in c.execute("SELECT * FROM steroid_doses WHERE substr(ts,1,10)=? ORDER BY ts", (ds,))],
            "excursions": [{k: x[k] for k in ("kind", "start", "end", "level", "peak_or_nadir", "duration_min")} |
                           {"possible_compression_artifact": x.get("possible_compression_artifact", False)}
                           for x in A.excursions(pts)],
            "wearable": s.toolbox.get_wearable_summary(ds),
        }

    @app.get("/api/record/{cite}")
    def record(cite: str, request: Request, response: Response):
        s = sess(request, response)
        kind, _, key = cite.partition(":")
        c = s.conn
        table = {"ins": "insulin_log", "meal": "meals", "rx": "medications", "ste": "steroid_doses", "j": "journal",
                 "site": "injection_sites"}.get(kind)
        row = None
        if table and key.isdigit():
            row = c.execute(f"SELECT * FROM {table} WHERE id=?", (int(key),)).fetchone()
        elif kind == "src":
            row = c.execute("SELECT * FROM evidence WHERE id=?", (key,)).fetchone()
        elif kind == "day":
            f = None
            try:
                f = A.day_features(c, date.fromisoformat(key))
            except ValueError:
                pass
            if f:
                return {"cite": cite, "kind": "day", **{k: v for k, v in f.items() if v is not None and k not in ("cite",)}}
        if not row:
            raise HTTPException(404, "No such record in the local database")
        return {"cite": cite, "kind": kind, **{k: row[k] for k in row.keys() if row[k] is not None}}

    @app.get("/api/pen-check")
    def pen_check(request: Request, response: Response):
        return sess(request, response).toolbox.pre_injection_checklist()

    @app.get("/api/pens")
    def pen_list(request: Request, response: Response):
        s = sess(request, response)
        last = s.conn.execute("SELECT MAX(substr(ts,1,10)) d FROM glucose").fetchone()["d"] or date.today().isoformat()
        meds = [m["name"] for m in s.toolbox.get_medications(last)["active_medications"]]
        match = set(pens.for_insulin(meds))
        return {"chosen": s.toolbox.get_pen(),
                "pens": [{"id": p["id"], "name": p["name"], "maker": p["maker"], "family": p["family"],
                          "insulin": p.get("insulin") or p.get("drug"), "matches": p["id"] in match}
                         for p in sorted(pens.ALL, key=lambda p: (p["id"] not in match, p["family"], p["maker"], p["name"]))]}

    @app.post("/api/pen")
    def choose_pen(body: PenIn, request: Request, response: Response):
        r = sess(request, response).toolbox.set_insulin_pen(body.pen)
        if not r["saved"]:
            raise HTTPException(422, r["error"])
        return r

    @app.get("/api/sites")
    def sites(request: Request, response: Response):
        return sess(request, response).toolbox.get_injection_sites() | {"names": ZONES}

    @app.post("/api/sites")
    def log_site(body: SiteIn, request: Request, response: Response):
        return sess(request, response).toolbox.log_injection_site(body.zone)

    @app.post("/api/journal")
    def add_journal(body: JournalIn, request: Request, response: Response):
        return sess(request, response).toolbox.add_journal(body.body, body.prompt)

    @app.get("/calendar.ics")
    def calendar(request: Request, response: Response):
        s = sess(request, response)
        write_ics(s.conn, s.ics)
        return FileResponse(s.ics, media_type="text/calendar", filename="prime.ics")

    @app.post("/api/reset")
    def reset(request: Request, response: Response):
        sessions.reset(sess(request, response).sid)
        return {"ok": True}

    # ---------------- model ----------------
    def check_budget(s: Session) -> None:
        with day_lock:
            if day["date"] != date.today():
                day.update(date=date.today(), n=0)
            if day["n"] >= per_day:
                raise HTTPException(429, "The demo has reached its daily model budget. Please try again tomorrow.")
        if s.calls >= per_session:
            raise HTTPException(429, f"This demo session is limited to {per_session} questions. Reset the demo to continue.")

    def spend(s: Session) -> None:
        s.calls += 1
        with day_lock:
            day["n"] += 1

    @app.post("/api/chat")
    def chat(body: ChatIn, request: Request, response: Response):
        s = sess(request, response)
        if EMERGENCY.search(body.message):                       # never depends on the model, the key, or the budget
            return {"text": EMERGENCY_REPLY, "trace": [], "guard": {"emergency": True}, "citations": {},
                    "remaining": per_session - s.calls}
        check_budget(s)
        with s.lock:
            try:
                if s.agent is None:
                    s.agent = Agent(llm_factory(settings, s.conn, Redactor(db.load_identity(s.conn))), s.toolbox)
                res = s.agent.ask(body.message, s.history)
            except RuntimeError as e:
                raise HTTPException(503, str(e))
            except Exception as e:
                raise HTTPException(502, f"The model request failed ({type(e).__name__}). Try again in a moment.")
            s.history[:] = s.history[-12:]
            if not res.guard.get("emergency"):
                spend(s)
        return {"text": res.text, "trace": res.trace, "guard": res.guard,
                "citations": cites.verify(s.conn, res.text),          # None => not found locally => 'unverified'
                "remaining": per_session - s.calls}

    @app.post("/api/pen-frames")
    def pen_frames(body: FramesIn, request: Request, response: Response):
        """A few frames cropped to the hands and pen -> one pen-check answer. Super-VL describes; vision.decide speaks."""
        s = sess(request, response)
        check_budget(s)
        dev = pens.get(s.toolbox.get_pen())
        cap_name = (dev or {}).get("cap_name") or "the cap over the needle end"
        done_visual = (dev or {}).get("done_visual") or "the pen window or counter shows the injection is finished"
        prompt = (vision.PROMPTS[body.check].replace("{n}", str(len(body.frames)))
                  .replace("{cap_name}", cap_name).replace("{done_visual}", done_visual))
        with s.lock:
            try:
                raw = llm_factory(settings, s.conn, Redactor(db.load_identity(s.conn))).vision(prompt, body.frames, purpose=f"pen-{body.check}")
            except RuntimeError as e:
                raise HTTPException(503, str(e))
            except Exception as e:
                raise HTTPException(502, f"The camera check failed ({type(e).__name__}). Use the step without the camera, and try again in a moment.")
            spend(s)
        obs = vision.parse(raw, body.check)
        no_drop = pens.no_drop_say(dev)                                            # the chosen pen's own retry rule
        return vision.decide(body.check, obs, no_drop, cap_name, done_visual) | {"observed": obs, "remaining": per_session - s.calls}

    # ---------------- CGM sensor check (profiles in cgm_data.py; the model only describes, cgm_vision.decide speaks) ----------------
    @app.get("/api/cgms")
    def cgm_list(request: Request, response: Response):
        return {"chosen": cgm.chosen(sess(request, response).conn), "cgms": cgm.listing()}

    @app.post("/api/cgm")
    def choose_cgm(body: CgmIn, request: Request, response: Response):
        r = cgm.choose(sess(request, response).conn, body.cgm)
        if not r["saved"]:
            raise HTTPException(422, r["error"])
        return r

    @app.get("/api/cgm-check")
    def cgm_check(request: Request, response: Response):
        """The spoken sensor-application steps for the chosen sensor (needs no model). No sensor chosen -> the general profile."""
        s = sess(request, response)
        c = cgm.profile_for(s.conn)
        last = cgm.last_site(s.conn)
        return {"cgm": {"id": c["id"], "name": c["name"], "maker": c["maker"], "coverage": c["coverage"], "chosen": cgm.chosen(s.conn) is not None},
                "steps": cgm.steps(c, last), "site": cgm.next_site(c, last), "after": c["after"], "caveat": c["caveat"],
                "sources": [{"title": t, "url": u} for t, u in c["sources"]], "checked": c["checked"],
                "reminder": "These steps are paraphrased from public instructions. Follow the instructions in your own sensor box, and ask your pharmacist or care team to watch you do it once."}

    @app.post("/api/cgm-done")
    def cgm_done(request: Request, response: Response):
        s = sess(request, response)
        return cgm.mark_done(s.conn, cgm.profile_for(s.conn))

    @app.post("/api/cgm-frames")
    def cgm_frames(body: CgmFramesIn, request: Request, response: Response):
        """One to three frames of the kit, skin or patch -> one sensor-check answer. The model describes; cgm_vision.decide speaks."""
        s = sess(request, response)
        check_budget(s)
        c = cgm.profile_for(s.conn)
        prompt = cgm_vision.prompt(body.check, c["keyword"])
        t0 = time.time()
        with s.lock:
            try:
                raw = llm_factory(settings, s.conn, Redactor(db.load_identity(s.conn))).vision(
                    prompt, body.frames, purpose=f"cgm-{body.check}", subject="your sensor kit, skin or patch")
            except RuntimeError as e:
                raise HTTPException(503, str(e))
            except Exception as e:
                raise HTTPException(502, f"The camera check failed ({type(e).__name__}). Use the step without the camera, and try again in a moment.")
            spend(s)
        obs = cgm_vision.parse(raw, body.check)
        return cgm_vision.decide(body.check, obs, c["name"], c["keyword"]) | {
            "observed": obs, "remaining": per_session - s.calls, "model": settings.vision_model, "seconds": round(time.time() - t0, 1)}

    @app.post("/api/visit-note")
    def visit_note_route(request: Request, response: Response):
        """The clinic visit note. Code computes the summary; Nemotron Ultra writes the note; the chat's guards check it."""
        s = sess(request, response)
        win = visit_note.window(s.conn)
        if not win:
            raise HTTPException(404, "There is no glucose data on this device yet.")
        check_budget(s)
        summary = s.toolbox.visit_summary(*win)
        with s.lock:
            try:
                llm = llm_factory(settings, s.conn, Redactor(db.load_identity(s.conn)))
                raw = llm.reason(visit_note.messages(summary))
            except RuntimeError as e:
                raise HTTPException(503, str(e))
            except Exception as e:
                raise HTTPException(502, f"The note could not be written ({type(e).__name__}). Try again in a moment.")
            spend(s)
        return visit_note.finish(s.conn, raw) | {"range": list(win), "model": settings.reason_model or settings.model, "remaining": per_session - s.calls}

    @app.post("/api/transcribe")
    async def transcribe(request: Request, response: Response):
        """A 16 kHz WAV from the page -> text, via Nemotron 3 Nano Omni. Not stored; the audit log notes the clip."""
        s = sess(request, response)
        if not settings.speech_model:
            raise HTTPException(503, "No speech model is configured.")
        wav = await request.body()
        if not wav or len(wav) > speech.MAX_BYTES:
            raise HTTPException(413, "That recording is empty or too long.")
        if s.speech >= speech_per_session:
            raise HTTPException(429, "This demo session has used its voice limit. Type your question, or reset the demo.")
        s.speech += 1

        def run():
            with s.lock:
                return llm_factory(settings, s.conn, Redactor(db.load_identity(s.conn))).transcribe(wav, speech.seconds_of(wav))
        try:
            text = await run_in_threadpool(run)
        except RuntimeError as e:
            raise HTTPException(503, str(e))
        except Exception as e:
            raise HTTPException(502, f"The speech model could not be reached ({type(e).__name__}).")
        return {"text": text}

    @app.get("/api/audit")
    def audit(request: Request, response: Response, n: int = 5):
        s = sess(request, response)
        rows = s.conn.execute("SELECT * FROM llm_audit ORDER BY id DESC LIMIT ?", (min(n, 20),)).fetchall()
        out = []
        for r in rows:
            payload = json.loads(r["sent"])
            counts: dict[str, int] = {}
            for m in PLACEHOLDER.findall(r["sent"]):
                counts[m] = counts.get(m, 0) + 1
            out.append({"id": r["id"], "ts": r["ts"], "model": r["model"], "purpose": r["purpose"], "chars": r["n_chars"],
                        "replaced": counts, "messages": payload["messages"]})
        return {"calls": out}

    return app
