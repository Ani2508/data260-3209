"""HW6 Part 2 - send 12 messages in one session, then fetch memory + aggregate.

Needs the backend on 8509, MongoDB and Ollama. Run: python3 code/run_hw06_part2.py
"""
import json
from datetime import datetime
from pathlib import Path

import requests
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports" / "hw06"
BASE = "http://localhost:8509"
USER, SESSION = "ani_demo", "ani-demo-s1"

MESSAGES = [
    "Hi, I'm Ani, a clinical trial coordinator. I need help tracking my study.",
    "My study is NCT05512874, a Phase II trial of an oral GLP-1 drug for type 2 diabetes.",
    "We want 240 participants in total and 61 are enrolled so far.",
    "What should I check before a screening visit?",
    "Our main site is in Sacramento and the PI is Dr. Helen Okafor.",
    "How do I report a serious adverse event?",
    "Participants on warfarin need extra INR checks during the study.",
    "Give me a short reminder text for a week-4 visit.",
    "The IRB continuing review is due on March 14.",
    "What documents does a sponsor monitor usually ask for?",
    "Which site and PI did I mention earlier?",
    "Summarize what you know about my trial in three bullets.",
]


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(HW / "RUN_LOG.txt", "a") as f:
        f.write(line + "\n")


def main():
    log("=" * 78)
    log(f"RUN: python3 code/run_hw06_part2.py   (HW6 Part 2, user={USER})   run by: Ani Taraiya")
    db = MongoClient("mongodb://localhost:27017")["s3209_doc"]       # start the demo user fresh
    removed = sum(db[c].delete_many({"user_id": USER}).deleted_count
                  for c in ("messages", "summaries", "episodes"))
    log(f"reset demo user {USER}: removed {removed} old docs")
    turns = []
    for i, msg in enumerate(MESSAGES, 1):
        r = requests.post(f"{BASE}/api/chat", json={"user_id": USER, "session_id": SESSION,
                                                    "message": msg}, timeout=900)
        r.raise_for_status()
        b = r.json()
        u = b["usage"]
        log(f"[{i:02d}] user: {msg}")
        log(f"     assistant: {b['reply'][:160]}")
        log(f"     used: short-term={b['used']['short_term']['count']} msgs | "
            f"session summary={'yes' if b['used']['long_term']['session_summary'] else 'no'} | "
            f"facts={[e['fact'] for e in b['used']['episodic_facts']]}")
        log(f"     tokens prompt={u['prompt_tokens']} completion={u['completion_tokens']} "
            f"latency={u['latency_ms']:.0f} ms new_summary={u['summary_created']}")
        turns.append(b)
    mem = requests.get(f"{BASE}/api/memory/{USER}").json()
    agg = requests.get(f"{BASE}/api/aggregate/{USER}").json()
    raw = HW / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "part2_chat_turns.json").write_text(json.dumps(turns, indent=2, default=str))
    (raw / "part2_memory.json").write_text(json.dumps(mem, indent=2, default=str))
    (raw / "part2_aggregate.json").write_text(json.dumps(agg, indent=2, default=str))
    log(f"GET /api/memory/{USER}: {len(mem['recent_messages'])} messages, "
        f"{len(mem['episodic_facts'])} facts, session summary={'yes' if mem['session_summary'] else 'no'}, "
        f"lifetime summary={'yes' if mem['lifetime_summary'] else 'no'}")
    log(f"GET /api/aggregate/{USER}: {agg['daily_message_counts']}")


if __name__ == "__main__":
    main()
