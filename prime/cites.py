"""Citation ids: scan text for them and resolve each against the local database.

A citation that does not resolve is shown to the user as 'unverified'. This is how the app catches a model
inventing a source or a record.
"""
from __future__ import annotations

import re
import sqlite3

CITE = re.compile(r"\[((?:day:\d{4}-\d{2}-\d{2})|(?:(?:ins|meal|rx|ste|j|site):\d+)|(?:src:[0-9a-f]{8}))\]")
ANY_CITE = re.compile(r"\b((?:day:\d{4}-\d{2}-\d{2})|(?:(?:ins|meal|rx|ste|j|site):\d+)|(?:src:[0-9a-f]{8}))\b")
# Some models write citations in CJK lenticular or full-width brackets: 【day:…】 or ［day:…］.
ALT_CITE = re.compile(r"[【［]\s*((?:day:\d{4}-\d{2}-\d{2})|(?:(?:ins|meal|rx|ste|j|site):\d+)|(?:src:[0-9a-f]{8}))\s*[】］]")


def normalize(text: str) -> str:
    """Rewrite alternative-bracket citations to the [id] form the rest of the app reads."""
    return ALT_CITE.sub(r"[\1]", text)


def find(text: str) -> list[str]:
    return sorted(set(CITE.findall(text)))


def find_any(text: str) -> list[str]:
    """Cite-looking ids anywhere (used on tool outputs, which carry them unbracketed inside JSON)."""
    return sorted(set(ANY_CITE.findall(text)))


def describe(conn: sqlite3.Connection, cite: str) -> str | None:
    """Short label for a citation, or None if it does not exist."""
    kind, _, key = cite.partition(":")
    c = conn
    if kind == "day":
        r = c.execute("SELECT COUNT(*) n FROM glucose WHERE substr(ts,1,10)=?", (key,)).fetchone()
        return f"Glucose, {key}" if r["n"] else None
    if kind in ("ins", "meal", "rx", "ste", "j", "site") and not key.isdigit():
        return None
    if kind == "ins":
        r = c.execute("SELECT * FROM insulin_log WHERE id=?", (int(key),)).fetchone()
        return f"Insulin {r['units']:g} units, {r['ts'][:10]}" if r else None
    if kind == "meal":
        r = c.execute("SELECT * FROM meals WHERE id=?", (int(key),)).fetchone()
        return f"{r['label']}, {r['ts'][:10]}" if r else None
    if kind == "rx":
        r = c.execute("SELECT * FROM medications WHERE id=?", (int(key),)).fetchone()
        return f"{r['name']} {r['dose'] or ''}".strip() if r else None
    if kind == "ste":
        r = c.execute("SELECT * FROM steroid_doses WHERE id=?", (int(key),)).fetchone()
        return f"{r['drug'].capitalize()} {r['dose_mg']:g} mg, {r['ts'][:10]}" if r else None
    if kind == "site":
        from .sites import ZONES
        r = c.execute("SELECT * FROM injection_sites WHERE id=?", (int(key),)).fetchone()
        return f"Injection site, {ZONES.get(r['zone'], r['zone']).replace('your ', '')}, {r['ts'][:10]}" if r else None
    if kind == "j":
        r = c.execute("SELECT ts FROM journal WHERE id=?", (int(key),)).fetchone()
        return f"Journal, {r['ts'][:10]}" if r else None
    if kind == "src":
        r = c.execute("SELECT title, source, year FROM evidence WHERE id=?", (key,)).fetchone()
        if not r:
            return None
        yr = f", {r['year']}" if r["year"] and r["year"] != "n.d." else ""
        return f"{r['title']} ({r['source']}{yr})"
    return None


def verify(conn: sqlite3.Connection, text: str) -> dict[str, str | None]:
    return {c: describe(conn, c) for c in find(text)}
