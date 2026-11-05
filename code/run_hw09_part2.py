"""HW9 Part 2 demo: 12 domain queries through the semantic cache in front of the HW8 agents.

Needs: Redis (make hw09-redis-up), Kafka + topics (make hw08-up, make hw08-topics),
the three agents (make hw09-planner / hw09-writer / hw09-reviewer) and Ollama.
Run: python3 code/run_hw09_part2.py [--threshold 0.85] [--keep]
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import redis
from sqlalchemy import text

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)
ROOT = Path(__file__).resolve().parent
for sub in ("semantic_cache", "kafka_agents", "web_application", "cache"):
    sys.path.insert(0, str(ROOT / sub))

from database import engine  # noqa: E402
from pipeline import AgentPipeline  # noqa: E402
from qa_service import QAService  # noqa: E402
from semantic_cache import INDEX, KEY_PREFIX, Embedder, SemanticCache  # noqa: E402
from trial_cache import REDIS_URL  # noqa: E402

RUN_BY = "Ani Taraiya"
RAW = ROOT.parent / "reports" / "hw09" / "raw"


def pick_trials() -> tuple[str, str]:
    """Return the NCT ids of the two lowest-id trials in s3209_rel."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT nct_id FROM trials ORDER BY id LIMIT 2")).all()
    if len(rows) < 2:
        raise SystemExit("Need at least 2 trials in s3209_rel.trials")
    return rows[0][0], rows[1][0]


def build_queries(a: str, b: str) -> list[tuple[str, str]]:
    """Return 12 (kind, question) pairs: new questions, exact duplicates and paraphrases."""
    general = "What should a patient check before joining a recruiting Phase II clinical trial?"
    return [
        ("new", f"What is the current status of trial {a}?"),
        ("exact", f"What is the current status of trial {a}?"),
        ("paraphrase", f"What's the status of clinical trial {a} right now?"),
        ("new", f"How many enrollment slots does trial {a} have?"),
        ("paraphrase", f"How many enrollment slots are there in trial {a}?"),
        ("new", f"Which sponsor runs trial {b}?"),
        ("exact", f"Which sponsor runs trial {b}?"),
        ("paraphrase", f"Which organization sponsors trial {b}?"),
        ("new", general),
        ("paraphrase", "Before enrolling in a recruiting Phase II trial, "
                       "what should a patient check?"),
        ("new", "What does a Terminated status mean for a clinical trial listing?"),
        ("exact", general),
    ]


def avg(values: list[float]) -> float:
    """Return the mean of values rounded to 0.1 (0.0 for an empty list)."""
    return round(sum(values) / len(values), 1) if values else 0.0


def main() -> None:
    """Return nothing; run the queries, print each result and the summary, save raw files."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--keep", action="store_true", help="do not clear the cache first")
    args = parser.parse_args()

    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    t = time.perf_counter()
    embedder = Embedder()
    print(f"Embedder {embedder.model_name} dim={embedder.dim} "
          f"loaded in {(time.perf_counter() - t) * 1000:.0f} ms")
    cache = SemanticCache(client, embedder.dim, args.threshold)
    created = cache.ensure_index()
    print(f"Redis index {INDEX} ({'created' if created else 'exists'}) prefix={KEY_PREFIX} "
          f"COSINE threshold={args.threshold}")
    if not args.keep:
        print(f"Cache cleared: {cache.reset()} entries deleted")
    service = QAService(cache, embedder, AgentPipeline())

    a, b = pick_trials()
    results = []
    for n, (kind, question) in enumerate(build_queries(a, b), 1):
        print(f"\nQ{n:02d} [{kind}] {question}")
        r = service.answer(question)
        steps = " | ".join(f"{k[:-3]} {v}" for k, v in r["timings"].items())
        print(f"     -> is_cached={r['is_cached']}  similarity={r['similarity']:.4f}  "
              f"latency={r['latency_ms']} ms  review={r['agent_status']}  ({steps})")
        if r["is_cached"]:
            print(f"     matched: {r['matched_query']}")
        print(f"     answer: {r['answer'][:110]}...")
        results.append({"n": n, "kind": kind, **{k: v for k, v in r.items() if k != "timings"},
                        **r["timings"]})

    hits = [r for r in results if r["is_cached"]]
    misses = [r for r in results if not r["is_cached"]]
    print(f"\n=== Summary: {len(results)} queries, threshold {args.threshold} ===")
    print(f"{'#':>3}  {'kind':<11}{'is_cached':<11}{'similarity':>10}{'latency ms':>12}")
    for r in results:
        print(f"{r['n']:>3}  {r['kind']:<11}{r['is_cached']!s:<11}{r['similarity']:>10.4f}"
              f"{r['latency_ms']:>12.1f}")
    print(f"Cache hit rate: {len(hits)} / {len(results)} = {100 * len(hits) / len(results):.1f}%")
    print(f"Avg latency cached:     {avg([r['latency_ms'] for r in hits]):>9.1f} ms "
          f"(n={len(hits)})")
    print(f"Avg latency non-cached: {avg([r['latency_ms'] for r in misses]):>9.1f} ms "
          f"(n={len(misses)})")

    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part2_results.json").write_text(json.dumps(results, indent=2) + "\n")
    with open(RAW / "part2_results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print("Saved reports/hw09/raw/part2_results.json and part2_results.csv")


if __name__ == "__main__":
    main()
