"""HW9 Part 2: look up the s3209_rel trial records a question names (by NCT id).

The facts are passed to the HW8 Writer, and a hash of the same fields forms the
data-version marker stored with each cached answer.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

VERSION_FIELDS = ("nct_id", "trial_title", "status", "enrollment_slots", "sponsor")
NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
WEB_APP = Path(__file__).resolve().parents[1] / "web_application"
TRIAL_SQL = ("SELECT t.id, t.nct_id, t.trial_title, t.status, t.enrollment_slots, "
             "s.name AS sponsor, t.updated_at FROM trials t "
             "JOIN sponsors s ON s.id = t.sponsor_id WHERE t.nct_id = :nct")


def extract_nct_ids(question: str) -> list[str]:
    """Return the distinct NCT ids in the question, upper-case, in order of appearance."""
    found: list[str] = []
    for match in NCT_RE.findall(question or ""):
        if match.upper() not in found:
            found.append(match.upper())
    return found


def data_version(rows: list[dict]) -> str:
    """Return the data-version marker 'trial_id@hash;...' over the answer fields, or 'none'."""
    if not rows:
        return "none"
    return ";".join(f"{r['id']}@{record_hash(r)}" for r in rows)


def record_hash(row: dict) -> str:
    """Return an 8-char hash of the fields an answer uses (view_count/updated_at excluded)."""
    text = "|".join(str(row[k]) for k in VERSION_FIELDS)
    return hashlib.sha1(text.encode()).hexdigest()[:8]


def facts_text(rows: list[dict]) -> str:
    """Return one plain-text line of facts per trial row ('' when there are none)."""
    return "\n".join(
        f"- {r['nct_id']}: title '{r['trial_title']}'; status {r['status']}; "
        f"enrollment slots {r['enrollment_slots']}; sponsor {r['sponsor']}" for r in rows)


def fetch_trials(nct_ids: list[str]) -> list[dict]:
    """Return the trial rows (with sponsor name) for the given NCT ids that exist."""
    if not nct_ids:
        return []
    if str(WEB_APP) not in sys.path:
        sys.path.insert(0, str(WEB_APP))
    from sqlalchemy import text

    from database import engine

    rows = []
    with engine.connect() as conn:
        for nct in nct_ids:
            row = conn.execute(text(TRIAL_SQL), {"nct": nct}).mappings().first()
            if row is not None:
                rows.append(dict(row))
    return rows


def find_trial_facts(question: str) -> dict:
    """Return {'trial_ids', 'facts', 'data_version'} for the trials named in the question."""
    rows = fetch_trials(extract_nct_ids(question))
    return {"trial_ids": [r["id"] for r in rows], "facts": facts_text(rows),
            "data_version": data_version(rows)}
