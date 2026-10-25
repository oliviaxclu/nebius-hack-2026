"""CGM sensor profiles: the spoken sensor-application check follows the person's own sensor.

Each profile in cgm_data.CGMS comes from that sensor's published instructions and lists its sources. A sensor with no
published insertion steps (or one a clinician places) is "limited": Prime checks only the kit, the skin prep and the
finished patch, and says so. Nothing here is a glucose reading or advice: profiles only describe putting the device on.
"""
from __future__ import annotations

from .cgm_data import CGMS

BY_ID = {c["id"]: c for c in CGMS}
GENERIC_SITE = "Use a different spot than last time."


def get(cgm_id: str | None) -> dict | None:
    return BY_ID.get(cgm_id or "")


# ---- the person's chosen sensor and last site live in the existing profile table (like the pen) ----
def chosen(conn) -> str | None:
    r = conn.execute("SELECT value FROM profile WHERE key='cgm'").fetchone()
    return r["value"] if r and get(r["value"]) else None


def choose(conn, cgm_id: str | None) -> dict:
    if cgm_id and not get(cgm_id):
        return {"saved": False, "error": "Unknown sensor. Use one of: " + ", ".join(BY_ID)}
    if cgm_id:
        conn.execute("INSERT OR REPLACE INTO profile(key,value) VALUES ('cgm',?)", (cgm_id,))
    else:
        conn.execute("DELETE FROM profile WHERE key='cgm'")
    conn.commit()
    return {"saved": True, "readback": f"Your sensor is now {get(cgm_id)['name']}." if cgm_id else "I'll use the general sensor steps."}


def last_site(conn) -> str | None:
    r = conn.execute("SELECT value FROM profile WHERE key='cgm_last_site'").fetchone()
    return r["value"] if r else None


def mark_done(conn, c: dict) -> dict:
    """Remember today's site so the next sensor goes somewhere else. A sensor with no published site stores nothing."""
    site = next_site(c, last_site(conn))
    if site:
        conn.execute("INSERT OR REPLACE INTO profile(key,value) VALUES ('cgm_last_site',?)", (site,))
        conn.commit()
    return {"saved": True, "site": site, "readback": f"Logged. Next time I'll suggest a different spot than the {site}." if site else "Logged."}


def profile_for(conn) -> dict:
    """The chosen sensor, or the general 'other' profile when none is chosen."""
    return get(chosen(conn)) or BY_ID["other"]


def listing() -> list[dict]:
    """What a sensor picker needs, grouped by maker in catalog order."""
    return [{"id": c["id"], "name": c["name"], "maker": c["maker"], "coverage": c["coverage"], "caveat": c["caveat"]} for c in CGMS]


def next_site(c: dict, last_site: str | None) -> str | None:
    """Rotate through this sensor's published sites. None when the sources name no specific site."""
    sites = c["sites"]
    if not sites:
        return None
    return sites[(sites.index(last_site) + 1) % len(sites)] if last_site in sites else sites[0]


def site_line(c: dict, last_site: str | None) -> str:
    site = next_site(c, last_site)
    return f"Today, use the {site}." if site else GENERIC_SITE


def steps(c: dict, last_site: str | None = None) -> list[dict]:
    """The sensor check for sensor `c`, with today's site filled in. Each step: say (fixed text), check (a cgm_vision checkpoint)."""
    line = site_line(c, last_site)
    return [{"say": s["say"].replace("{site}", line), "check": s["check"]} for s in c["steps"]]


def passage(c: dict) -> dict:
    """An evidence passage for one sensor, written from its profile only (for the model's search tool)."""
    bits = [f"{c['name']} ({c['maker']}) sensor application, practice flow."]
    if c["caveat"]:
        bits.append(c["caveat"])
    else:
        bits.append("Steps: " + " ".join(s["say"].replace("{site}", "").strip() for s in c["steps"]))
    title, url = c["sources"][0] if c["sources"] else ("Instructions in the sensor box", "")
    return dict(topic="cgm-model", title=f"{c['name']}: applying the sensor", source=title, year=c["checked"][:4],
                evidence_level="manufacturer", text=" ".join(bits)[:880], url=url)
