from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from . import db, evidence, synthetic
from .agent import Agent
from .config import load_settings
from .llm import LLM
from .privacy import Redactor
from .tools import TOOL_NAMES, Toolbox


def _ctx():
    s = load_settings()
    conn = db.connect(s.db_path)
    return s, conn, Toolbox(conn, s.ics_path)


def _agent(s, conn, tb):
    return Agent(LLM(s, conn, Redactor(db.load_identity(conn))), tb)


def cmd_demo(a):
    s, conn, tb = _ctx()
    if a.fresh:
        conn.close()
        for p in (s.db_path,):
            p.unlink(missing_ok=True)
        conn = db.connect(s.db_path)
    sc = synthetic.Scenario(failure_days=None if a.no_failure else (12, 19), seed=a.seed)
    data = synthetic.build(date.today(), sc)
    counts = synthetic.load_into(conn, data)
    n_ev = evidence.load_evidence(conn)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    synthetic.write_truth(out / "ground_truth.json", data)
    print(f"Synthetic patient loaded into {s.db_path}\n  {counts}\n  evidence passages: {n_ev}\n  ground truth (do not show the agent): {out/'ground_truth.json'}")
    print(f"  data covers {data['first_day']} to {data['today']}")


def cmd_tool(a):
    s, conn, tb = _ctx()
    args = json.loads(a.args or "{}")
    if a.name not in TOOL_NAMES:
        print("unknown tool; choose from:", ", ".join(sorted(TOOL_NAMES)))
        return 2
    print(json.dumps(json.loads(tb.dispatch(a.name, args)), indent=2, ensure_ascii=False))


def cmd_ask(a):
    s, conn, tb = _ctx()
    res = _agent(s, conn, tb).ask(" ".join(a.question))
    print(res.text)
    if a.trace:
        print("\n-- tool calls --")
        for t in res.trace:
            print(f"  {t['tool']}({json.dumps(t['args'])}) -> {t['result_chars']} chars")
        if res.guard:
            print("-- guard --", res.guard)


def cmd_chat(a):
    s, conn, tb = _ctx()
    agent, history = _agent(s, conn, tb), []
    print("Prime chat (Ctrl-D to exit). Your data stays in", s.db_path)
    while True:
        try:
            q = input("\nyou> ").strip()
        except EOFError:
            break
        if q:
            print("\n" + agent.ask(q, history).text)


def cmd_audit(a):
    s, conn, _ = _ctx()
    rows = conn.execute("SELECT * FROM llm_audit ORDER BY id DESC LIMIT ?", (a.n,)).fetchall()
    if not rows:
        print("Nothing has been sent to the hosted model yet.")
    for r in rows:
        print(f"[{r['ts']}] {r['model']} purpose={r['purpose']} {r['n_chars']} chars sent")
        if a.full:
            print(json.dumps(json.loads(r["sent"]), indent=2, ensure_ascii=False))


def cmd_status(a):
    s, conn, _ = _ctx()
    print(f"home: {s.home}\nmodel: {s.model}\nbase_url: {s.base_url}\nkey set: {bool(s.api_key)}")
    for t in ("glucose", "medications", "steroid_doses", "insulin_log", "meals", "wearable_daily", "journal", "reminders", "evidence", "llm_audit"):
        print(f"  {t}: {conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")


def cmd_check(a):
    s, conn, _ = _ctx()
    llm = LLM(s, conn, Redactor({}))
    models = llm.list_models()
    nvidia = [m for m in models if m.lower().startswith("nvidia/")]
    print(f"{len(models)} models visible; NVIDIA models: {nvidia}")
    print(f"configured model {s.model!r} listed: {s.model in models}")
    print("round trip:", llm.ping())


def cmd_evals(a):
    from .evals import main as run
    return run(live=a.live)


def main(argv=None):
    p = argparse.ArgumentParser(prog="prime", description="Local-first glucose explainer (Nemotron on Nebius Token Factory)")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo", help="load the synthetic patient (no real data)")
    d.add_argument("--out", default="demo_data"); d.add_argument("--fresh", action="store_true", help="delete the local DB first")
    d.add_argument("--no-failure", action="store_true", help="counterfactual: insulin always delivered"); d.add_argument("--seed", type=int, default=7)
    d.set_defaults(f=cmd_demo)
    t = sub.add_parser("tool", help="call one tool directly (no API key needed)"); t.add_argument("name"); t.add_argument("--args", default="{}"); t.set_defaults(f=cmd_tool)
    q = sub.add_parser("ask", help="ask the agent one question"); q.add_argument("question", nargs="+"); q.add_argument("--trace", action="store_true"); q.set_defaults(f=cmd_ask)
    sub.add_parser("chat", help="interactive chat").set_defaults(f=cmd_chat)
    au = sub.add_parser("audit", help="show what was sent to the hosted model"); au.add_argument("-n", type=int, default=5); au.add_argument("--full", action="store_true"); au.set_defaults(f=cmd_audit)
    sub.add_parser("status", help="local store summary").set_defaults(f=cmd_status)
    sub.add_parser("check", help="verify Token Factory key + model").set_defaults(f=cmd_check)
    e = sub.add_parser("evals", help="run the evaluation suite"); e.add_argument("--live", action="store_true", help="also test the real model (needs a key)"); e.set_defaults(f=cmd_evals)
    a = p.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
