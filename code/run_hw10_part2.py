"""HW10 Part 2: send test questions through the cache + HW8 agents, then evaluate each trace.

Needs: Redis, Kafka + topics, the three agents (make hw10-planner / -writer / -reviewer),
MySQL and Ollama (agent model + judge model).
Run: python3 code/run_hw10_part2.py [--judge-model llama3.1:8b]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)
ROOT = Path(__file__).resolve().parent
for sub in ("semantic_cache", "kafka_agents", "web_application", "cache", "tracing",
            "evaluation"):
    sys.path.insert(0, str(ROOT / sub))

RUN_BY = "Ani Taraiya"
RAW = ROOT.parent / "reports" / "hw10" / "raw"


def questions(nct: str) -> list[str]:
    """Return the end-to-end test questions (one names a real trial from s3209_rel)."""
    return [
        "What should a coordinator check before enrolling a patient in a recruiting "
        "Phase II type 2 diabetes trial?",
        f"What is the current status and sponsor of trial {nct}, and can it still enroll?",
        "How should a site explain the difference between Recruiting and "
        "Active, not recruiting to a patient?",
    ]


def show(r: dict) -> None:
    """Return nothing; print one evaluation record."""
    print(f"  trace_id: {r['trace_id']}   status={r['status']}")
    if r.get("error"):
        print(f"  error: {r['error']}")
    s = r.get("scores")
    if not s:
        return
    print(f"  plan:  {r['plan']}")
    print(f"  draft: {r['draft'][:150]}...")
    print(f"  final ({r['review_status']}): {r['final_answer'][:150]}...")
    for key in ("plan_quality", "writer_helpfulness", "final_helpfulness"):
        print(f"  {key:<19} {s[key]['score']}/5  {str(s[key]['reason'])[:140]}")
    imp = s["improvement"]
    print(f"  improvement        draft {imp['draft_score']} -> final {imp['final_score']} "
          f"(diff {imp['diff']})  same_text={imp['same_text']}")
    print(f"  interpretation: {imp['interpretation']}")


def pick(r: dict, key: str):
    """Return the 1-5 score for key (the diff for 'improvement'), or None."""
    s = r.get("scores", {}).get(key, {})
    return s.get("diff") if key == "improvement" else s.get("score")


def main() -> None:
    """Return nothing; run each question, evaluate its trace, print and save the results."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge-model", default=None)
    args = parser.parse_args()
    if args.judge_model:
        os.environ["JUDGE_MODEL"] = args.judge_model

    import redis
    from sqlalchemy import text

    from database import engine
    from evaluator import evaluate_trace
    from judge import LocalJudge, settings
    from pipeline import AgentPipeline
    from qa_service import QAService
    from semantic_cache import Embedder, SemanticCache
    from trial_cache import REDIS_URL

    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Judge: {json.dumps(settings())}")
    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    embedder = Embedder()
    cache = SemanticCache(client, embedder.dim)
    cache.ensure_index()
    service = QAService(cache, embedder, AgentPipeline(), store=False)
    judge = LocalJudge()
    with engine.connect() as conn:
        nct = conn.execute(text("SELECT nct_id FROM trials ORDER BY id LIMIT 1")).scalar_one()

    records = []
    for n, q in enumerate(questions(nct), 1):
        print(f"\nQ{n} {q}")
        r = service.answer(q)
        print(f"  cache={'HIT' if r['is_cached'] else 'MISS'} sim={r['similarity']:.4f} "
              f"latency={r['latency_ms']} ms review={r['agent_status']}")
        if r["is_cached"]:
            print("  cache hit: no Planner/Writer/Reviewer messages to evaluate, skipped")
            continue
        rec = evaluate_trace(r["trace_id"], r["started_ms"], judge=judge)
        show(rec)
        records.append(rec)

    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "part2_eval.json").write_text(json.dumps(records, indent=2) + "\n")
    ok = [r for r in records if r["status"] == "ok"]
    print(f"\n=== Summary: {len(records)} traces evaluated, {len(ok)} ok ===")
    print(f"{'trace_id':<38}{'plan':>5}{'draft':>6}{'final':>6}{'diff':>6}  review")
    for r in records:
        p, d, f, diff = (pick(r, k) for k in ("plan_quality", "writer_helpfulness",
                                               "final_helpfulness", "improvement"))
        print(f"{r['trace_id']:<38}{p!s:>5}{d!s:>6}{f!s:>6}{diff!s:>6}  {r.get('review_status')}")
    print("Saved reports/hw10/raw/part2_eval.json and eval_results.jsonl")


if __name__ == "__main__":
    main()
