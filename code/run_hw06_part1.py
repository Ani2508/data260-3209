"""HW6 Part 1 - exercise the MongoDB document API (CRUD + validation errors).

Needs the backend on 8509 and MongoDB. Run: python3 code/run_hw06_part1.py
"""
import json
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports" / "hw06"
URL = "http://localhost:8509/api/doc/trials"

SAMPLES = [
    {"title": "Oral GLP-1 Agonist in Type 2 Diabetes", "phase": "phase_2", "status": "recruiting",
     "description": "Randomized, double-blind study of an oral GLP-1 agonist over 26 weeks.",
     "start_date": "2026-11-02T09:00:00"},
    {"title": "Low-Dose Aspirin After Stent Placement", "phase": "phase_3", "status": "active",
     "description": "Compares 75 mg vs 150 mg aspirin for 12 months.", "start_date": "2026-06-15T08:30:00"},
    {"title": "Sleep Quality in Long COVID", "phase": "observational", "status": "completed",
     "start_date": "2025-09-01T10:00:00"},
]
INVALID = {
    "missing required title": {"phase": "phase_1", "start_date": "2026-12-01T09:00:00"},
    "invalid enum (status)": {"title": "Bad status", "phase": "phase_1", "status": "open",
                              "start_date": "2026-12-01T09:00:00"},
    "wrong type (start_date)": {"title": "Bad date", "phase": "phase_1", "start_date": "next monday"},
    "title over 100 chars": {"title": "T" * 101, "phase": "phase_1", "start_date": "2026-12-01T09:00:00"},
}


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line)
    with open(HW / "RUN_LOG.txt", "a") as f:
        f.write(line + "\n")


def show(label, r):
    body = r.json() if r.content else None
    log(f"{label:34s} -> {r.status_code}")
    if body is not None:
        print(json.dumps(body, indent=2, default=str)[:700])
    return body


def main():
    log("=" * 78)
    log("RUN: python3 code/run_hw06_part1.py   (HW6 Part 1, db s3209_doc.trials)   run by: Ani Taraiya")
    results = {}
    existing = {t["title"]: t for t in requests.get(URL, params={"limit": 200}).json()}
    ids = []
    for s in SAMPLES:                          # sample data stays for Compass screenshot
        if s["title"] in existing:
            ids.append(existing[s["title"]]["id"])
            continue
        body = show(f"POST {s['title'][:24]}", requests.post(URL, json=s))
        ids.append(body["id"])
    results["list"] = show("GET /api/doc/trials", requests.get(URL))
    results["get_one"] = show("GET /api/doc/trials/{id}", requests.get(f"{URL}/{ids[0]}"))
    results["update"] = show("PUT /api/doc/trials/{id}", requests.put(
        f"{URL}/{ids[0]}", json={"status": "active", "description": "Enrollment opened at 3 sites."}))
    tmp = requests.post(URL, json={"title": "Temporary trial to delete", "phase": "phase_4",
                                   "start_date": "2027-01-10T09:00:00"}).json()
    log(f"POST temporary trial               -> id {tmp['id']} (default status={tmp['status']})")
    show("DELETE /api/doc/trials/{id}", requests.delete(f"{URL}/{tmp['id']}"))
    results["after_delete"] = show("GET deleted id", requests.get(f"{URL}/{tmp['id']}"))
    results["bad_id"] = show("GET /api/doc/trials/not-an-id", requests.get(f"{URL}/not-an-id"))
    log("--- validation tests")
    for label, payload in INVALID.items():
        results[label] = show(f"POST {label}", requests.post(URL, json=payload))
    (HW / "raw").mkdir(parents=True, exist_ok=True)
    (HW / "raw" / "part1_crud.json").write_text(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
