"""Injection sites: where the person injected, which spot is next, and whether one spot is being overused.

Deterministic on purpose. The teaching it follows (see the "site" passages in evidence_data): pick one body
area and rotate within it, change the spot every time, stay 2 inches from the navel, and avoid lumpy, firm,
sore or bruised skin, because injecting into lumps changes how insulin is absorbed.
"""
from __future__ import annotations

# Zone id -> how Prime says it. Left and right are the PERSON's left and right.
ZONES = {
    "belly-upper-right": "the upper right of your belly",
    "belly-lower-right": "the lower right of your belly",
    "belly-lower-left": "the lower left of your belly",
    "belly-upper-left": "the upper left of your belly",
    "thigh-right": "the front of your right thigh, toward the outside",
    "thigh-left": "the front of your left thigh, toward the outside",
}
# Rotation order within each area (a clock around the navel; then right and left thigh).
AREAS = {
    "belly": ["belly-upper-right", "belly-lower-right", "belly-lower-left", "belly-upper-left"],
    "thigh": ["thigh-right", "thigh-left"],
}
OVERUSE_WINDOW, OVERUSE_COUNT = 7, 5          # the same zone for 5 of the last 7 injections

# Fixed, cited reminders (source titles are resolved to src ids by the caller).
CHECKS = [
    ("Stay at least two inches, about three finger-widths, from your belly button.", "Navel distance, scars, sore or lumpy spots"),
    ("Move at least one finger-width from your last spot.", "Lumps from injecting in the same spot"),
    ("Before you inject, feel the skin. Do not use a spot that is lumpy, firm, numb, sore or bruised.", "Navel distance, scars, sore or lumpy spots"),
]


def area_of(zone: str) -> str:
    return zone.split("-")[0]


def suggest(history: list[str], area: str | None = None) -> str:
    """Next zone: stay in the area used last (default belly), and pick its least recently used zone.
    `history` is newest first."""
    area = area or (area_of(history[0]) if history else "belly")
    zones = AREAS[area]
    # Higher = longer ago. A zone never used ranks oldest of all, earliest in clock order first.
    age = {z: history.index(z) if z in history else len(history) + len(zones) - zones.index(z) for z in zones}
    return max(zones, key=age.get)


def overuse(history: list[str]) -> dict | None:
    recent = history[:OVERUSE_WINDOW]
    if len(recent) < OVERUSE_COUNT:
        return None
    top = max(set(recent), key=recent.count)
    n = recent.count(top)
    return {"zone": top, "where": ZONES[top], "count": n, "of": len(recent)} if n >= OVERUSE_COUNT else None
