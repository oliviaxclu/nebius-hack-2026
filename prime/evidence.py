"""Evidence library: load curated passages into SQLite and search them (FTS5, BM25)."""
from __future__ import annotations

import hashlib
import re
import sqlite3

from .evidence_data import P

# Light query expansion so natural questions hit the right topic.
EXPAND = {
    "prednisone": "steroid glucocorticoid", "prednisolone": "steroid glucocorticoid", "steroids": "steroid glucocorticoid",
    "methylprednisolone": "steroid glucocorticoid", "dexamethasone": "steroid glucocorticoid", "cortisone": "steroid",
    "morning": "dawn fasting", "fasting": "dawn morning", "waking": "dawn morning",
    "ozempic": "glp1 semaglutide", "semaglutide": "glp1 gastric", "mounjaro": "glp1 tirzepatide", "tirzepatide": "glp1 gastric",
    "wegovy": "glp1 semaglutide", "glp-1": "glp1", "glp": "glp1",
    "needle": "pen cap prime", "cap": "pen needle prime", "priming": "pen prime safety", "prime": "pen safety test",
    "pen": "needle cap prime pen-model", "inject": "pen needle site", "injection": "pen needle site",
    "kwikpen": "pen-model", "flexpen": "pen-model", "flextouch": "pen-model", "solostar": "pen-model", "hold": "pen-model needle",
    "site": "site rotation injection", "sites": "site rotation", "rotate": "site rotation", "rotation": "site",
    "lump": "site lipohypertrophy", "lumps": "site lipohypertrophy", "lumpy": "site lipohypertrophy",
    "belly": "site navel", "stomach": "site navel", "abdomen": "site navel", "thigh": "site", "navel": "site",
    "blind": "accessibility visual impairment", "vision": "accessibility visual impairment", "sight": "accessibility visual",
    "low vision": "accessibility",
    "low": "hypoglycemia compression", "hypoglycemia": "low", "overnight": "night compression dawn",
    "breakfast": "meal-order", "protein": "meal-order", "vegetables": "meal-order", "carbs": "meal-order carbohydrate",
    "walk": "activity exercise", "walking": "activity exercise", "exercise": "activity",
    "sleep": "sleep insulin sensitivity", "insomnia": "sleep",
    "sensor": "cgm artifact accuracy", "libre": "cgm", "dexcom": "cgm",
    "pregnancy": "gestational placental", "placenta": "gestational placental",
    "taper": "steroid taper hypoglycemia", "tapering": "steroid taper",
}


STOP = {"the", "and", "was", "why", "this", "that", "with", "for", "from", "have", "has", "are", "what", "how", "when", "your",
        "you", "can", "did", "does", "not", "but", "about", "into", "after", "before", "over", "than", "high", "my", "should",
        "does", "make", "get", "got", "today", "yesterday", "afternoon", "went", "any", "there", "their", "them", "would",
        "could", "will", "tell", "help", "need", "know", "just", "like", "been", "being", "were", "which"}


def evidence_id(title: str) -> str:
    return hashlib.sha1(title.encode()).hexdigest()[:8]


def load_evidence(conn: sqlite3.Connection) -> int:
    """Idempotent: (re)loads the curated passages and rebuilds the FTS index."""
    conn.execute("DELETE FROM evidence")
    conn.execute("INSERT INTO evidence_fts(evidence_fts) VALUES ('delete-all')")
    for p in P:
        conn.execute(
            "INSERT INTO evidence(id,topic,title,source,year,evidence_level,text,url) VALUES (?,?,?,?,?,?,?,?)",
            (evidence_id(p["title"]), p["topic"], p["title"], p["source"], p["year"], p["evidence_level"], p["text"], p["url"]))
    conn.execute("INSERT INTO evidence_fts(rowid, topic, title, text) SELECT rowid, topic, title, text FROM evidence")
    conn.commit()
    return len(P)


def _tokens(question: str) -> list[str]:
    toks = re.findall(r"[A-Za-z0-9\-]{3,}", question.lower())
    out: list[str] = []
    for t in toks:
        if t in STOP:
            continue
        out.append(t)
        out += EXPAND.get(t, "").split()
    seen, uniq = set(), []
    for t in out:
        t = t.replace("-", "")
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def search_evidence(conn: sqlite3.Connection, question: str, k: int = 4) -> list[dict]:
    toks = _tokens(question)
    if not toks:
        return []
    match = " OR ".join(f'"{t}"' for t in toks)
    try:
        rows = conn.execute(
            """SELECT e.* FROM evidence_fts f JOIN evidence e ON e.rowid = f.rowid
               WHERE evidence_fts MATCH ? ORDER BY bm25(evidence_fts, 6.0, 4.0, 1.0) LIMIT 30""", (match,)).fetchall()
    except sqlite3.OperationalError:
        return []
    out, per_topic = [], {}
    for r in rows:
        if per_topic.get(r["topic"], 0) >= 2:        # diversity: at most two per topic
            continue
        per_topic[r["topic"]] = per_topic.get(r["topic"], 0) + 1
        out.append({"cite": f"src:{r['id']}", "title": r["title"], "source": r["source"], "year": r["year"],
                    "evidence_level": r["evidence_level"], "text": r["text"], "url": r["url"], "topic": r["topic"]})
        if len(out) >= k:
            break
    return out


def get_by_title(conn: sqlite3.Connection, fragment: str) -> dict | None:
    r = conn.execute("SELECT * FROM evidence WHERE title LIKE ? LIMIT 1", (f"%{fragment}%",)).fetchone()
    return None if not r else {"cite": f"src:{r['id']}", "title": r["title"], "source": r["source"], "url": r["url"]}
