"""HW9 Part 4: self-improving Answering + Evaluator agents.

  demo      4.1 controlled revision (initial answer forced to be incomplete)
  train     4.2 training_data.json; repeated failure patterns become lessons
  validate  4.3 validation_data.json before/after each lesson; keep or remove it
  test      4.4 test_data.json on the four variants
  lessons   print data/lessons.json

Run: python3 code/run_hw09_part4.py demo|train|validate|test|lessons
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "self_improving"))
sys.path.insert(0, str(ROOT.parent / "src"))

from agents import AnsweringAgent, EvaluatorAgent  # noqa: E402
from lessons import LessonStore  # noqa: E402
from model_client import ModelClient  # noqa: E402
from reference import DATA, load_json  # noqa: E402
from system import run_question  # noqa: E402

RUN_BY = "Ani Taraiya"
SEED = 3209
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
RAW = ROOT.parent / "reports" / "hw09" / "raw"
LESSONS = DATA / "lessons.json"
CANDIDATES = RAW / "part4_lessons_candidates.json"
DEMO_Q = "What is the current status of trial NCT48236558?"
DEMO_BAD = "Trial NCT48236558 is a Phase II hypertension study sponsored by Stanford Medicine."


def header(title: str) -> tuple[AnsweringAgent, EvaluatorAgent]:
    """Return the two agents after printing the run header."""
    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}   {title}")
    print(f"model={MODEL} temperature=0 seed={SEED}   reference=data/reference_data.json")
    ref = load_json("reference_data.json")
    llm = ModelClient(model=MODEL, temperature=0.0, seed=SEED)
    return AnsweringAgent(llm, ref), EvaluatorAgent(llm, ref)


def save(name: str, data) -> None:
    """Return nothing; write one raw JSON result file."""
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / name).write_text(json.dumps(data, indent=2, default=str) + "\n")
    print(f"Saved reports/hw09/raw/{name}")


def run_set(rows: list[dict], answerer, evaluator, store, attempts: int,
            learn: bool = False, quiet: bool = False) -> list[dict]:
    """Return the traces for every question in a dataset."""
    out = []
    for row in rows:
        out.append(run_question(row["id"], row["question"], answerer, evaluator, store,
                                attempts, learn, log=(lambda *_: None) if quiet else print))
    return out


def demo() -> None:
    """Return nothing; show one full revision sequence (4.1)."""
    answerer, evaluator = header("4.1 controlled revision")
    trace = run_question("DEMO", DEMO_Q, answerer, evaluator, None, 2, forced_first=DEMO_BAD)
    first, last = trace["trace"][0], trace["trace"][-1]
    print("\n--- revision sequence ---")
    print(f"Question          : {DEMO_Q}")
    print(f"Initial answer    : {first['answer']}")
    print(f"Evaluation 1      : {first['result']} - {first['explanation']}")
    print(f"Evaluator feedback: {first['feedback']}")
    print(f"Revised answer    : {last['answer']}")
    print(f"Final evaluation  : {last['result']} - {last['explanation']}")
    print(f"Attempts          : {trace['attempts']}")
    print(f"Final response    : {trace['final_answer']}")
    save("part4_revision_demo.json", trace)


def train() -> None:
    """Return nothing; run the training set with lesson creation and reuse (4.2)."""
    answerer, evaluator = header("4.2 training run (lessons created and reused)")
    LESSONS.write_text("[]\n")
    store = LessonStore(LESSONS)
    traces = run_set(load_json("training_data.json"), answerer, evaluator, store, 2, learn=True)
    print("\n--- lessons.json ---")
    print(json.dumps(store.lessons, indent=2))
    reused = [t for t in traces if t["lessons_used"]]
    print(f"Questions that loaded a lesson: {', '.join(t['id'] for t in reused) or 'none'}")
    save("part4_train.json", traces)
    save(CANDIDATES.name, store.lessons)


def first_pass(traces: list[dict]) -> dict:
    """Return {question id: first-attempt result}."""
    return {t["id"]: t["first_result"] for t in traces}


def validate() -> None:
    """Return nothing; keep each lesson only if validation does not regress (4.3)."""
    answerer, evaluator = header("4.3 validation (first attempt, no repair)")
    rows = load_json("validation_data.json")
    types = {r["id"]: None for r in rows}
    candidates = json.loads(CANDIDATES.read_text())
    kept: list[dict] = []
    before = run_set(rows, answerer, evaluator, LessonStore(lessons=[], persist=False), 1,
                     quiet=True)
    for t in before:
        types[t["id"]] = t["type"]
    report = []
    print(f"Before (no lessons): {sum(v == 'PASS' for v in first_pass(before).values())}"
          f"/{len(rows)} PASS")
    for cand in candidates:
        trial = LessonStore(lessons=kept + [cand], persist=False)
        after = run_set(rows, answerer, evaluator, trial, 1, quiet=True)
        b, a = first_pass(before), first_pass(after)
        fixed = [q for q in b if b[q] == "REVISE" and a[q] == "PASS"]
        broke = [q for q in b if b[q] == "PASS" and a[q] == "REVISE"]
        unrelated_bad = [q for q in a if types[q] == "unrelated" and a[q] == "REVISE"]
        failures_ok = sum(v == "REVISE" for v in a.values()) <= sum(v == "REVISE"
                                                                   for v in b.values())
        keep = failures_ok and not broke and not unrelated_bad
        print(f"\n{cand['lesson_id']} ({cand['pattern']})")
        print(f"  {'id':<4} {'type':<14} before  after")
        for q in b:
            print(f"  {q:<4} {types[q]:<14} {b[q]:<7} {a[q]}")
        print(f"  fixed={fixed or '-'}  regressions={broke or '-'}  "
              f"unrelated unsupported={unrelated_bad or '-'}")
        print(f"  failures before={sum(v == 'REVISE' for v in b.values())} "
              f"after={sum(v == 'REVISE' for v in a.values())}  -> "
              f"{'KEEP' if keep else 'REMOVE'}")
        report.append({"lesson_id": cand["lesson_id"], "pattern": cand["pattern"],
                       "before": b, "after": a, "fixed": fixed, "regressions": broke,
                       "unrelated_unsupported": unrelated_bad, "kept": keep})
        if keep:
            kept.append(cand)
            before = after
    store = LessonStore(LESSONS, lessons=kept)
    store.save()
    print(f"\nlessons.json now holds: {[x['lesson_id'] for x in kept] or 'no lessons'}")
    save("part4_validation.json", report)


VARIANTS = (("Baseline", 1, "none"), ("Evaluator Repair", 2, "none"),
            ("Lesson Memory", 2, "all"), ("Validated Improvement", 2, "validated"))


def test() -> None:
    """Return nothing; run the held-out test set on the four variants (4.4)."""
    answerer, evaluator = header("4.4 test set on four variants")
    rows = load_json("test_data.json")
    results, summary = [], []
    for name, attempts, source in VARIANTS:
        lessons = {"none": [], "all": json.loads(CANDIDATES.read_text()),
                   "validated": json.loads(LESSONS.read_text())}[source]
        print(f"\n=== {name}: max_attempts={attempts}, lessons="
              f"{[x['lesson_id'] for x in lessons] or 'none'} ===")
        traces = run_set(rows, answerer, evaluator, LessonStore(lessons=lessons, persist=False),
                         attempts, quiet=True)
        for t in traces:
            print(f"  {t['id']} {t['type']:<14} first={t['first_result']:<6} "
                  f"final={t['final_result']:<6} attempts={t['attempts']} "
                  f"{t['latency_ms']:>8.1f} ms  {t['final_answer'][:70]}")
            results.append({"variant": name, **{k: v for k, v in t.items() if k != "trace"}})
        correct = sum(t["final_result"] == "PASS" for t in traces)
        summary.append({"variant": name, "correct": correct, "incorrect": len(traces) - correct,
                        "avg_attempts": round(sum(t["attempts"] for t in traces) / len(traces), 2),
                        "avg_latency_ms": round(sum(t["latency_ms"] for t in traces)
                                                / len(traces), 1)})
    print(f"\n=== Test results ({len(rows)} questions, test_data.json) ===")
    print(f"{'Variant':<22}{'Correct':>8}{'Incorrect':>10}{'Avg attempts':>14}"
          f"{'Avg latency ms':>16}")
    for s in summary:
        print(f"{s['variant']:<22}{s['correct']:>8}{s['incorrect']:>10}{s['avg_attempts']:>14}"
              f"{s['avg_latency_ms']:>16}")
    save("part4_test_results.json", results)
    save("part4_test_summary.json", summary)
    with open(RAW / "part4_test_summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)


def show_lessons() -> None:
    """Return nothing; print the current lessons.json."""
    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("code/self_improving/data/lessons.json")
    print(LESSONS.read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("demo", "train", "validate", "test", "lessons"))
    mode = parser.parse_args().mode
    {"demo": demo, "train": train, "validate": validate, "test": test,
     "lessons": show_lessons}[mode]()
