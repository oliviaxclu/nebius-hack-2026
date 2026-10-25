"""Local SQLite store. Everything the user owns lives in this one file."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS glucose(
  ts TEXT PRIMARY KEY,             -- naive ISO 'YYYY-MM-DDTHH:MM:SS'
  mgdl REAL NOT NULL,
  source TEXT NOT NULL DEFAULT 'libre'
);

CREATE TABLE IF NOT EXISTS medications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL, drug_class TEXT, dose TEXT, route TEXT, schedule TEXT,
  start TEXT NOT NULL, end TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS steroid_doses(      -- one row per dose taken
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, drug TEXT NOT NULL, route TEXT, dose_mg REAL NOT NULL, source TEXT
);

CREATE TABLE IF NOT EXISTS insulin_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, units REAL NOT NULL, insulin TEXT NOT NULL,
  source TEXT,                     -- voice | manual | pen
  confirmed INTEGER,               -- user confirmed the dose by read-back
  steps_checked INTEGER,           -- completed the pre-injection check (NULL = not asked)
  note TEXT
);

CREATE TABLE IF NOT EXISTS meals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, label TEXT NOT NULL,
  carbs_g REAL, protein_g REAL, fiber_g REAL,
  carbs_last INTEGER DEFAULT 0,    -- vegetables/protein eaten before carbohydrate
  source TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS wearable_daily(
  date TEXT PRIMARY KEY,
  sleep_h REAL, sleep_quality INTEGER, steps INTEGER, active_min INTEGER,
  resting_hr INTEGER, walk_after_dinner_min INTEGER
);

CREATE TABLE IF NOT EXISTS profile(key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS identity(
  key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(key, value)
);

CREATE TABLE IF NOT EXISTS journal(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, prompt TEXT, body TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS journal_fts USING fts5(
  body, prompt, content='journal', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS journal_ai AFTER INSERT ON journal BEGIN
  INSERT INTO journal_fts(rowid, body, prompt) VALUES (new.id, new.body, new.prompt);
END;

CREATE TABLE IF NOT EXISTS reminders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL, due TEXT NOT NULL, repeat TEXT, notes TEXT,
  kind TEXT DEFAULT 'general', created TEXT NOT NULL
);

-- Where each injection went (zone ids from sites.ZONES). Powers rotation and overuse reminders.
CREATE TABLE IF NOT EXISTS injection_sites(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, zone TEXT NOT NULL, source TEXT
);

-- Curated medical evidence (paraphrased summaries with sources). Searched by search_medical_evidence.
CREATE TABLE IF NOT EXISTS evidence(
  id TEXT PRIMARY KEY,             -- 8 hex chars, stable per title
  topic TEXT NOT NULL, title TEXT NOT NULL, source TEXT NOT NULL,
  year TEXT, evidence_level TEXT NOT NULL, text TEXT NOT NULL, url TEXT
);
CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
  topic, title, text, content='evidence', content_rowid='rowid'
);

-- Every payload sent to the hosted model, post-redaction. Powers the "what left my device" panel.
CREATE TABLE IF NOT EXISTS llm_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL, model TEXT, purpose TEXT, sent TEXT NOT NULL, n_chars INTEGER
);
"""


def connect(path: Path | str, check_same_thread: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def save_identity(conn: sqlite3.Connection, identity: dict[str, list[str]]) -> None:
    for key, values in identity.items():
        for v in values:
            if v:
                conn.execute("INSERT OR IGNORE INTO identity(key,value) VALUES (?,?)", (key, v))
    conn.commit()


def load_identity(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in conn.execute("SELECT key, value FROM identity"):
        out.setdefault(r["key"], []).append(r["value"])
    return out


def load_profile(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM profile")}
