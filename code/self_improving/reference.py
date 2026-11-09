"""HW9 Part 4: reference dataset access and question analysis (no model calls)."""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
NCT_RE = re.compile(r"\bNCT\d{8}\b", re.IGNORECASE)
FIELD_WORDS = (  # checked in this order ("enrollment slots" must win over "enroll")
    ("enrollment_slots", ("slot", "spots", "openings")),
    ("sponsor", ("sponsor", "runs trial", "organization", "organisation")),
    ("phase", ("phase",)),
    ("condition", ("condition", "disease")),
    ("status", ("status", "recruiting", "accepting", "open for", "join", "enrol")),
)
FIELD_TYPE = {"status": "trial_status", "enrollment_slots": "trial_slots",
              "sponsor": "trial_sponsor", "phase": "trial_other", "condition": "trial_other"}
TERMS = ("Active - Not Recruiting", "Recruiting", "Completed", "Terminated",
         "Phase III", "Phase II", "Phase I", "Observational")


def load_json(name: str):
    """Return the parsed JSON file from the data folder."""
    return json.loads((DATA / name).read_text())


def norm(text: str) -> str:
    """Return lower-case text with punctuation turned into single spaces."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).split())


def find_trial(ref: dict, nct_id: str) -> dict | None:
    """Return the reference record for an NCT id, or None if it is not listed."""
    return next((t for t in ref["trials"] if t["nct_id"] == nct_id.upper()), None)


def asked_field(question: str) -> str | None:
    """Return the record field a trial question asks about (None if unclear)."""
    q = question.lower()
    for field, words in FIELD_WORDS:
        if any(w in q for w in words):
            return field
    return None


def definition_term(question: str) -> str | None:
    """Return the status or phase name a definition question asks about, if any."""
    q = f" {norm(question)} "
    for term in TERMS:
        if f" {norm(term)} " in q:
            return term
    return None


def analyze(question: str, ref: dict) -> dict:
    """Return the question type, NCT ids, matching records and asked field."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    ids = list(dict.fromkeys(m.upper() for m in NCT_RE.findall(question)))
    known = [r for r in (find_trial(ref, i) for i in ids) if r]
    unknown = [i for i in ids if not find_trial(ref, i)]
    field, term = asked_field(question), None
    if ids:
        qtype = "unknown_trial" if unknown else FIELD_TYPE.get(field, "trial_other")
    else:
        term = definition_term(question)
        meaning = any(w in question.lower() for w in ("mean", "what is a", "definition"))
        qtype = "definition" if term and meaning else "unrelated"
    return {"type": qtype, "nct_ids": ids, "known": known, "unknown": unknown,
            "field": field, "term": term}


def catalogue_entry(rec: dict) -> str:
    """Return the public listing line of a trial (static fields only)."""
    return f"{rec['nct_id']}: {rec['title']} (sponsor {rec['sponsor']})"


def reference_block(info: dict, ref: dict) -> str:
    """Return the reference facts that apply to an analyzed question."""
    lines = [f"{r['nct_id']}: title '{r['title']}'; phase {r['phase']}; condition "
             f"{r['condition']}; status {r['status']}; enrollment slots "
             f"{r['enrollment_slots']}; sponsor {r['sponsor']}" for r in info["known"]]
    lines += [f"{i}: not in the reference dataset (not listed)" for i in info["unknown"]]
    if info["term"]:
        lines.append(f"{info['term']}: {ref['definitions'][info['term']]}")
    return "\n".join(lines) or "No catalogue record applies to this question."
