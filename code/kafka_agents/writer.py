"""HW8 Writer: s3209_tasks (plan) -> s3209_drafts (draft answer).

Part 3 flags turn one fix off each:  --no-idempotency  --commit-first  --no-dead-letter
WRITER_SIM=1 (ordering test only): a seeded sleep replaces the model call.
"""
import argparse
import os
import time

from common import DRAFTS, TASKS, ask_json, log, model, now
from reliable import run_reliable

SYSTEM = ("You are the Writer for a clinical trial listings help desk. Answer the question "
          "in 60-120 words, following the plan in order. Be factual and plain. "
          "If trial records are given, use only their values for status, enrollment slots "
          "and sponsor, and never invent trial IDs, dates or counts; still answer in full "
          "sentences that name the trial and state the value. "
          'Reply only with JSON: {"answer": "..."}')
SIM = os.getenv("WRITER_SIM") == "1"
llm = None if SIM else model()
NAME = "WRITER"


def handle(msg: dict) -> dict:
    plan = "\n".join(f"{i}. {s}" for i, s in enumerate(msg["plan"], 1))
    if SIM:
        time.sleep(msg.get("work_ms", 200) / 1000)
        draft = {"answer": f"draft for {msg.get('entity')} update {msg.get('seq')}"}
    else:
        facts = msg.get("facts", "")
        records = f"\nTrial records:\n{facts}" if facts else ""
        draft = ask_json(llm, SYSTEM, f"Question: {msg['question']}{records}\nPlan:\n{plan}",
                         "answer")
    log(NAME, f"DRAFT    {len(draft['answer'].split())} words")
    return {**msg, "draft": draft["answer"], "written_at": now()}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="WRITER")
    p.add_argument("--no-idempotency", action="store_true")
    p.add_argument("--commit-first", action="store_true")
    p.add_argument("--no-dead-letter", action="store_true")
    a = p.parse_args()
    NAME = a.name
    run_reliable(a.name, TASKS, DRAFTS, handle, idempotent=not a.no_idempotency,
                 commit_first=a.commit_first, dead_letter=not a.no_dead_letter)
