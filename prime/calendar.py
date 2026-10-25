"""Export reminders to a standard .ics file the user can subscribe to / import (Apple, Google, Outlook)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

RRULE = {"daily": "FREQ=DAILY", "weekly": "FREQ=WEEKLY", "monthly": "FREQ=MONTHLY"}


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fmt(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return d.strftime("%Y%m%dT%H%M%S")


def write_ics(conn: sqlite3.Connection, path: Path) -> int:
    rows = conn.execute("SELECT * FROM reminders ORDER BY due").fetchall()
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Prime//Local Health Assistant//EN", "CALSCALE:GREGORIAN"]
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    for r in rows:
        lines += [
            "BEGIN:VEVENT",
            f"UID:prime-{r['id']}@local",
            f"DTSTAMP:{stamp}",
            f"DTSTART:{_fmt(r['due'])}",
            f"SUMMARY:{_esc(r['title'])}",
        ]
        if r["notes"]:
            lines.append(f"DESCRIPTION:{_esc(r['notes'])}")
        if r["repeat"] in RRULE:
            lines.append(f"RRULE:{RRULE[r['repeat']]}")
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc(r['title'])}", "TRIGGER:-PT10M", "END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    path.write_text("\r\n".join(lines) + "\r\n")
    return len(rows)
