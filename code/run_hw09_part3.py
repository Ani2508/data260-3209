"""HW9 Part 3: threshold sweep, one false hit in full, and stale answers + invalidation.

  sweep     seed the cache once, then run the 40 labeled cases at 0.75-0.95
  show      print the saved sweep rows for one threshold
  falsehit  show one false hit from the sweep with the correct answer
  stale     cache an answer, update the s3209_rel record, show the stale hit, then invalidate

Needs Redis, MySQL, Kafka, the three HW8 agents and Ollama (same as Part 2).
Run: python3 code/run_hw09_part3.py sweep | falsehit [--threshold 0.85] | stale
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)
ROOT = Path(__file__).resolve().parent
for sub in ("semantic_cache", "kafka_agents", "web_application", "cache"):
    sys.path.insert(0, str(ROOT / sub))

import redis  # noqa: E402
import yaml  # noqa: E402
from sqlalchemy import text  # noqa: E402

from database import engine  # noqa: E402
from pipeline import AgentPipeline  # noqa: E402
from qa_service import QAService  # noqa: E402
from semantic_cache import Embedder, SemanticCache  # noqa: E402
from trial_cache import REDIS_URL  # noqa: E402
from trial_facts import current_version, fetch_trials, find_trial_facts  # noqa: E402

RUN_BY = "Ani Taraiya"
REPORTS = ROOT.parent / "reports" / "hw09"
CASES = REPORTS / "cases" / "cache_cases.yaml"
RAW = REPORTS / "raw"
THRESHOLDS = (0.75, 0.80, 0.85, 0.90, 0.95)
MISS_COST = 1.0    # one full agent run (3 model calls, ~2.6 s)
FALSE_HIT_COST = 20.0  # a wrong trial fact sent to a coordinator: correction + support follow-up
STALE_NCT = "NCT30565986"
STALE_STATUS = "Terminated"


def setup(threshold: float) -> tuple[SemanticCache, Embedder, AgentPipeline]:
    """Return a connected cache, embedder and agent pipeline."""
    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    embedder = Embedder()
    cache = SemanticCache(client, embedder.dim, threshold)
    cache.ensure_index()
    return cache, embedder, AgentPipeline()


def seed_cache(cache: SemanticCache, embedder: Embedder, pipeline: AgentPipeline,
               seeds: list[dict]) -> None:
    """Return nothing; store one agent answer per seed query (no lookup, always stored)."""
    print(f"Cache cleared: {cache.reset()} entries; seeding {len(seeds)} queries")
    for s in seeds:
        facts = find_trial_facts(s["query"])
        final = pipeline.ask(s["query"], facts["facts"])
        cache.store(s["query"], embedder.encode(s["query"]), final.get("answer", ""),
                    facts["data_version"], facts["trial_ids"], final.get("status", ""))
        print(f"  {s['id']} stored  version={facts['data_version']:<12} {s['query']}")


def classify(case: dict, result: dict, seed_by_query: dict) -> str:
    """Return TP (right hit), FALSE_HIT, FALSE_MISS or TN (right miss) for one case."""
    if result["is_cached"]:
        matched = seed_by_query.get(result["matched_query"])
        right = case["expect"] == "hit" and matched == case.get("seed")
        return "TP" if right else "FALSE_HIT"
    return "FALSE_MISS" if case["expect"] == "hit" else "TN"


def sweep() -> None:
    """Return nothing; run every labeled case at each threshold and print the summary table."""
    data = yaml.safe_load(CASES.read_text())
    seeds, cases = data["seeds"], data["cases"]
    cache, embedder, pipeline = setup(THRESHOLDS[0])
    print(f"Cases: {CASES.relative_to(ROOT.parent)}  seeds={len(seeds)}  cases={len(cases)}")
    seed_cache(cache, embedder, pipeline, seeds)
    seed_by_query = {s["query"]: s["id"] for s in seeds}
    service = QAService(cache, embedder, pipeline, store=False)

    rows, summary = [], []
    for th in THRESHOLDS:
        cache.threshold = th
        print(f"\n=== threshold {th:.2f} ===")
        counts = {"TP": 0, "FALSE_HIT": 0, "FALSE_MISS": 0, "TN": 0}
        latencies = []
        for case in cases:
            r = service.answer(case["query"])
            outcome = classify(case, r, seed_by_query)
            counts[outcome] += 1
            latencies.append(r["latency_ms"])
            matched = seed_by_query.get(r["matched_query"], "-")
            print(f"  {case['id']} {case['group']:<10} expect={case['expect']:<4} "
                  f"{'HIT ' if r['is_cached'] else 'MISS'} sim={r['similarity']:.4f} "
                  f"nearest={matched:<4} {r['latency_ms']:>8.1f} ms  {outcome}")
            rows.append({"threshold": th, **case, "is_cached": r["is_cached"],
                         "similarity": r["similarity"], "nearest_seed": matched,
                         "matched_query": r["matched_query"], "answer": r["answer"],
                         "latency_ms": r["latency_ms"], "outcome": outcome})
        hits = counts["TP"] + counts["FALSE_HIT"]
        misses = len(cases) - hits
        summary.append({
            "threshold": th, "hits": hits, "hit_rate": round(100 * hits / len(cases), 1),
            "false_hits": counts["FALSE_HIT"],
            "false_hit_rate": round(100 * counts["FALSE_HIT"] / hits, 1) if hits else 0.0,
            "false_misses": counts["FALSE_MISS"], "misses": misses,
            "mean_latency_ms": round(sum(latencies) / len(latencies), 1),
            "total_cost": misses * MISS_COST + counts["FALSE_HIT"] * FALSE_HIT_COST})

    print(f"\n=== Threshold sweep: {len(cases)} cases, cost = misses x {MISS_COST:g} "
          f"+ false hits x {FALSE_HIT_COST:g} ===")
    print(f"{'threshold':>9} {'hit rate':>9} {'false-hit rate':>15} {'false hits':>11} "
          f"{'false misses':>13} {'mean ms':>9} {'total cost':>11}")
    for s in summary:
        print(f"{s['threshold']:>9.2f} {s['hit_rate']:>8.1f}% {s['false_hit_rate']:>14.1f}% "
              f"{s['false_hits']:>11} {s['false_misses']:>13} {s['mean_latency_ms']:>9.1f} "
              f"{s['total_cost']:>11.1f}")
    best = min(summary, key=lambda s: (s["total_cost"], -s["threshold"]))
    print(f"Lowest total cost: threshold {best['threshold']:.2f} (cost {best['total_cost']:.1f})")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part3_sweep_cases.json").write_text(json.dumps(rows, indent=2) + "\n")
    (RAW / "part3_sweep_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("Saved reports/hw09/raw/part3_sweep_cases.json and part3_sweep_summary.json")


def falsehit(threshold: float) -> None:
    """Return nothing; print one false hit from the sweep with the correct answer."""
    rows = json.loads((RAW / "part3_sweep_cases.json").read_text())
    found = [r for r in rows if r["threshold"] == threshold and r["outcome"] == "FALSE_HIT"]
    if not found:
        raise SystemExit(f"no false hit at threshold {threshold}")
    fh = sorted(found, key=lambda r: (r["group"] != "similar", -r["similarity"]))[0]
    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"False hits at threshold {threshold:.2f}: {len(found)} "
          f"({', '.join(r['id'] for r in found)})\n")
    print(f"Case            : {fh['id']} [{fh['group']}] expect={fh['expect']}")
    print(f"Incoming query  : {fh['query']}")
    print(f"Cached query    : {fh['matched_query']}")
    print(f"Similarity      : {fh['similarity']:.4f}  (threshold {threshold:.2f})")
    print(f"Cached answer   : {fh['answer']}")
    facts = find_trial_facts(fh["query"])
    print(f"Record (s3209_rel): {facts['facts'].lstrip('- ') or 'no trial record'}")
    pipeline = AgentPipeline()
    correct = pipeline.ask(fh["query"], facts["facts"])
    print(f"Correct answer  : {correct.get('answer', '')}")
    a, b = set(fh["query"].lower().split()), set(fh["matched_query"].lower().split())
    print(f"Words only in incoming: {sorted(a - b)}   only in cached: {sorted(b - a)}")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part3_false_hit.json").write_text(json.dumps(
        {**fh, "correct_answer": correct.get("answer", ""), "record": facts["facts"]},
        indent=2) + "\n")
    print("Saved reports/hw09/raw/part3_false_hit.json")


def show(threshold: float) -> None:
    """Return nothing; print the saved sweep rows for one threshold as a compact table."""
    path = RAW / "part3_sweep_cases.json"
    rows = [r for r in json.loads(path.read_text()) if r["threshold"] == threshold]
    if not rows:
        raise SystemExit(f"no sweep rows for threshold {threshold}")
    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Sweep results at threshold {threshold:.2f} from {path.relative_to(ROOT.parent)} "
          f"(sweep run {datetime.fromtimestamp(path.stat().st_mtime):%Y-%m-%d %H:%M})")
    print(f"{'case':<5}{'group':<11}{'expect':<7}{'result':<7}{'sim':>7}  {'nearest':<8}"
          f"{'ms':>8}  outcome")
    for r in rows:
        result = "HIT" if r["is_cached"] else "MISS"
        print(f"{r['id']:<5}{r['group']:<11}{r['expect']:<7}{result:<7}{r['similarity']:>7.4f}  "
              f"{r['nearest_seed']:<8}{r['latency_ms']:>8.1f}  {r['outcome']}")
    labels = ("TP", "FALSE_HIT", "FALSE_MISS", "TN")
    counts = {k: sum(r["outcome"] == k for r in rows) for k in labels}
    print("  ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"\n{'threshold':>9} {'hit rate':>9} {'false-hit rate':>15} {'mean ms':>9} "
          f"{'total cost':>11}")
    for t in json.loads((RAW / "part3_sweep_summary.json").read_text()):
        print(f"{t['threshold']:>9.2f} {t['hit_rate']:>8.1f}% {t['false_hit_rate']:>14.1f}% "
              f"{t['mean_latency_ms']:>9.1f} {t['total_cost']:>11.1f}")


def set_status(nct: str, status: str) -> None:
    """Return nothing; update one trial's status (and updated_at) in s3209_rel."""
    with engine.begin() as conn:
        conn.execute(text("UPDATE trials SET status = :s, updated_at = NOW() WHERE nct_id = :n"),
                     {"s": status, "n": nct})


def stale(keep_update: bool) -> None:
    """Return nothing; demonstrate a stale hit and the data-version invalidation."""
    cache, embedder, pipeline = setup(0.85)
    question = f"What is the current status of trial {STALE_NCT}?"
    plain = QAService(cache, embedder, pipeline)                       # no version check
    checked = QAService(cache, embedder, pipeline, check_version=True)  # invalidation on
    row = fetch_trials([STALE_NCT])[0]
    original = row["status"]
    print(f"Cache cleared: {cache.reset()} entries   question: {question}")
    print(f"Record trials.id={row['id']} {STALE_NCT}: status={original}")
    log = []

    def step(name: str, service: QAService) -> None:
        r = service.answer(question)
        db = fetch_trials([STALE_NCT])[0]["status"]
        print(f"  -> is_cached={r['is_cached']} sim={r['similarity']:.4f} "
              f"version={r['data_version']} invalidated={r['stale_invalidated']} "
              f"latency={r['latency_ms']} ms")
        print(f"     answer: {r['answer']}")
        print(f"     DB status now: {db}")
        log.append({"step": name, **{k: r[k] for k in ("is_cached", "similarity", "answer",
                    "data_version", "stale_invalidated", "latency_ms")}, "db_status": db})

    print("\n[1] First ask -> miss, answer cached with data_version")
    step("first ask", plain)
    print(f"\n[2] UPDATE trials SET status='{STALE_STATUS}' WHERE nct_id='{STALE_NCT}'")
    set_status(STALE_NCT, STALE_STATUS)
    time.sleep(0.2)
    print(f"     data_version now: {current_version([row['id']])}")
    print("\n[3] Ask again, no invalidation -> STALE HIT (old answer)")
    step("stale hit", plain)
    print("\n[4] Ask again, invalidation on -> version mismatch, entry deleted, agents re-run")
    step("invalidated", checked)
    print("\n[5] Ask again, invalidation on -> fresh hit")
    step("fresh hit", checked)
    if not keep_update:
        set_status(STALE_NCT, original)
        print(f"\nRestored {STALE_NCT} status={original}; cache cleared: {cache.reset()} entries")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part3_stale.json").write_text(json.dumps(log, indent=2) + "\n")
    print("Saved reports/hw09/raw/part3_stale.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("sweep", "show", "falsehit", "stale"))
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--keep-update", action="store_true")
    args = parser.parse_args()
    if args.mode == "sweep":
        sweep()
    elif args.mode == "show":
        show(args.threshold)
    elif args.mode == "falsehit":
        falsehit(args.threshold)
    else:
        stale(args.keep_update)
