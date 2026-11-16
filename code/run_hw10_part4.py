"""HW10 Part 4: trace examples and the 50-request cache-miss latency experiment.

  traces   one cache-miss trace (full agent path + evaluator), one cache-hit trace,
           one failed trace (fault injected in the Writer -> dead letter)
           -> reports/hw10/raw/traces.json
  show     print the journey of one trace:  show --trace-id <id>
  latency  50 confirmed cache misses (pre-screened + verified), each evaluated
           -> part4_latency_runs.csv, part4_latency_summary.json
  table    recompute the p50/p95 table from the saved spans

Run: python3 code/run_hw10_part4.py traces | show --trace-id X | latency | table
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "evaluation"))

from runtime import RAW, RUN_BY, build_service, trial_ids  # noqa: E402
from tracer import journey, load_spans  # noqa: E402

TRACES = RAW / "traces.json"
RUNS_CSV = RAW / "part4_latency_runs.csv"
SUMMARY = RAW / "part4_latency_summary.json"
N_REQUESTS = 50
TABLE_STAGES = ("cache_lookup", "planner", "writer", "reviewer", "queue_wait", "evaluator")
QUEUES = ("inbox", "tasks", "drafts", "final")
MISS_QUESTIONS = [
    "What should a coordinator review before a site initiation visit for a new trial?",
    "How should a coordinator record a protocol deviation in a trial log?",
    "What should a coordinator tell a patient about trial visit reimbursement?",
    "What checks should a site do before shipping lab samples for a trial?",
]
FAIL_QUESTION = "What should a coordinator prepare before a sponsor monitoring visit?"


def print_journey(tid: str) -> None:
    """Return nothing; print one trace's spans in stage order."""
    spans = journey(load_spans(trace_id=tid))
    if not spans:
        print(f"no spans for {tid}")
        return
    route = next((s["attrs"].get("result") for s in spans if s["stage"] == "cache_lookup"), "?")
    print(f"\ntrace_id={tid}  cache={str(route).upper()}  spans={len(spans)}")
    print(f"{'stage':<13}{'start':<14}{'end':<14}{'ms':>9}  {'status':<7}error")
    for s in spans:
        print(f"{s['stage']:<13}{s['start'][11:23]:<14}{s['end'][11:23]:<14}"
              f"{s['duration_ms']:>9.1f}  {s['status']:<7}{s['error'] or ''}")


def traces() -> None:
    """Return nothing; capture the miss, hit and failed traces and save their ids."""
    from evaluator import evaluate_trace

    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    service, _, _ = build_service(store=True, timeout_s=120)
    out = {}
    for q in MISS_QUESTIONS:  # first question that is not cached yet
        r = service.answer(q)
        if not r["is_cached"]:
            rec = evaluate_trace(r["trace_id"], r["started_ms"])
            print(f"MISS  {r['trace_id']}  review={r['agent_status']}  eval={rec['status']}")
            out["miss"] = {"trace_id": r["trace_id"], "question": q}
            break
        print(f"(already cached, trying next) {q}")
    else:
        raise SystemExit("all miss candidates are cached; add a new question")
    q = out["miss"]["question"]
    r = service.answer(q)  # same question again -> served from the semantic cache
    print(f"HIT   {r['trace_id']}  is_cached={r['is_cached']}  sim={r['similarity']:.4f}")
    out["hit"] = {"trace_id": r["trace_id"], "question": q}
    service.store = False
    tid = str(uuid.uuid4())
    try:
        service.answer(FAIL_QUESTION, trace_id=tid, fail_stage="writer")
        raise SystemExit("failed trace did not fail")
    except (RuntimeError, TimeoutError) as exc:
        print(f"FAIL  {tid}  {type(exc).__name__}: {exc}")
        out["failed"] = {"trace_id": tid, "question": FAIL_QUESTION, "error": str(exc)}
    TRACES.write_text(json.dumps(out, indent=2) + "\n")
    for kind in ("hit", "miss", "failed"):
        print_journey(out[kind]["trace_id"])
    print(f"\nSaved {TRACES.name}")


def candidates() -> list[str]:
    """Return candidate questions for the latency run (more than 50, all different)."""
    ids = trial_ids(12)
    topics = ["the current status", "the sponsor", "the number of enrollment slots",
              "whether it is still recruiting", "a two-sentence summary"]
    out = [f"For trial {n}, what is {t}?" for n in ids for t in topics]
    out += [f"As a coordinator, how do I handle {x}?" for x in (
        "a missed study visit", "an adverse event report", "a consent form update",
        "a screen failure", "a participant moving away", "a lost lab sample",
        "a late sponsor payment", "an expired lab certificate", "a translator request",
        "a pregnancy during a trial")]
    return out


def latency() -> None:
    """Return nothing; run 50 verified cache misses with evaluation and save timings."""
    from evaluator import evaluate_trace

    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    service, cache, embedder = build_service(store=False)
    picked = []
    for q in candidates():  # pre-screen: skip anything the cache would serve
        best = cache.nearest(embedder.encode(q))
        if not best or best["similarity"] < cache.threshold:
            picked.append(q)
        if len(picked) == N_REQUESTS:
            break
    if len(picked) < N_REQUESTS:
        raise SystemExit(f"only {len(picked)} uncached candidates")
    print(f"Pre-screen: {N_REQUESTS} questions below threshold {cache.threshold}; "
          f"store=False so the run adds nothing to the cache")
    rows = []
    for n, q in enumerate(picked, 1):
        r = service.answer(q)
        if r["is_cached"]:
            raise SystemExit(f"request {n} was served from cache: {q}")
        rec = evaluate_trace(r["trace_id"], r["started_ms"])
        time.sleep(0.3)  # let the agents flush their last span lines
        row = breakdown(r["trace_id"])
        row.update(n=n, is_cached=r["is_cached"], similarity=r["similarity"],
                   eval_status=rec["status"])
        rows.append(row)
        print(f"{n:>2} MISS sim={r['similarity']:.3f} e2e={row['e2e_ms']:>8.1f} ms  "
              f"plan={row['planner']:>7.1f} write={row['writer']:>7.1f} "
              f"review={row['reviewer']:>7.1f} queue={row['queue_wait']:>6.1f} "
              f"eval={row['evaluator']:>8.1f}  {q[:50]}")
    with open(RUNS_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nAll {len(rows)} requests: is_cached=False (verified per request)")
    summarize([r["trace_id"] for r in rows])


def breakdown(tid: str) -> dict:
    """Return per-stage milliseconds for one trace (sums repeated spans per stage)."""
    spans = load_spans(trace_id=tid)
    ms = {}
    for s in spans:
        ms[s["stage"]] = ms.get(s["stage"], 0.0) + s["duration_ms"]
    req = next(s for s in spans if s["stage"] == "request")
    end = max(s["end_ms"] for s in spans)
    row = {"trace_id": tid, **{k: round(ms.get(k, 0.0), 1) for k in
                               ("cache_lookup", "facts", "planner", "writer", "reviewer",
                                "evaluator", *QUEUES)}}
    row["queue_wait"] = round(sum(ms.get(k, 0.0) for k in QUEUES), 1)
    row["request_ms"] = req["duration_ms"]
    row["e2e_ms"] = round(end - req["start_ms"], 1)  # cache lookup -> evaluator end
    return row


def pct(values: list[float], q: float) -> float:
    """Return the q-th percentile (linear interpolation) of values."""
    if not values:
        raise ValueError("no values")
    v = sorted(values)
    k = (len(v) - 1) * q / 100
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 1)


def summarize(tids: list[str]) -> dict:
    """Return and print the p50/p95/% table for the given traces; save the summary."""
    rows = [breakdown(t) for t in tids]
    total = sum(r["e2e_ms"] for r in rows)
    table = {}
    for st in (*TABLE_STAGES, "facts", "e2e_ms", "request_ms"):
        vals = [r[st] for r in rows]
        table[st] = {"p50": pct(vals, 50), "p95": pct(vals, 95),
                     "pct_of_e2e": round(100 * sum(vals) / total, 1)}
    other = 100 - sum(table[s]["pct_of_e2e"] for s in (*TABLE_STAGES, "facts"))
    hits = [s["duration_ms"] for s in load_spans()
            if s["stage"] == "request" and s["attrs"].get("route") == "hit"]
    summary = {"n": len(rows), "table": table, "other_pct": round(other, 1),
               "dominant": max(TABLE_STAGES, key=lambda s: table[s]["pct_of_e2e"]),
               "cache_hit_latency": {"n": len(hits),
                                     "p50": pct(hits, 50) if hits else None,
                                     "p95": pct(hits, 95) if hits else None},
               "trace_ids": tids, "e2e_definition": "request start -> evaluator span end"}
    SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")
    names = {"cache_lookup": "Cache lookup", "planner": "Planner", "writer": "Writer",
             "reviewer": "Reviewer", "queue_wait": "Queue wait (total)",
             "evaluator": "Evaluation", "facts": "Facts (MySQL)",
             "e2e_ms": "End-to-end", "request_ms": "User-facing (to final)"}
    print(f"\n=== Stage latency, {len(rows)} cache-miss requests ===")
    print(f"{'Stage':<24}{'p50 (ms)':>10}{'p95 (ms)':>10}{'% of e2e':>10}")
    for k, name in names.items():
        t = table[k]
        print(f"{name:<24}{t['p50']:>10.1f}{t['p95']:>10.1f}{t['pct_of_e2e']:>9.1f}%")
    print(f"{'Other (store, overhead)':<24}{'':>20}{summary['other_pct']:>9.1f}%")
    print(f"Dominant stage: {names[summary['dominant']]}")
    h = summary["cache_hit_latency"]
    print(f"Cache-hit latency (separate): n={h['n']} p50={h['p50']} ms p95={h['p95']} ms")
    print(f"Saved {SUMMARY.name}")
    return summary


def table() -> None:
    """Return nothing; recompute the table from the trace ids saved by 'latency'."""
    with open(RUNS_CSV, newline="") as fh:
        tids = [r["trace_id"] for r in csv.DictReader(fh)]
    summarize(tids)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["traces", "show", "latency", "table"])
    p.add_argument("--trace-id", default="")
    a = p.parse_args()
    if a.cmd == "show":
        print_journey(a.trace_id or json.loads(TRACES.read_text())["failed"]["trace_id"])
    else:
        {"traces": traces, "latency": latency, "table": table}[a.cmd]()
