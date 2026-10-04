"""HW5 Part 3 - retry demo + seeded fault injection (0%, 20%, 50% x 50 calls).

Usage:  python run_part3.py            (uses the s3209_rel MySQL data)
Writes: reports/hw05/raw/fault_injection_calls.csv
        reports/hw05/raw/fault_injection_summary.json
"""
import csv
import json
import math
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import trials_core as core
from resilience import (VERIFY_SEED, FaultyStore, ResilientStore, RetryPolicy,
                        TransientError, call_with_retry)
from tool_gateway import execute_tool

def log(msg: str = "") -> None:
    """print one line prefixed with a timestamp (goes to the console and RUN_LOG.txt via tee)."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


RAW = Path(__file__).resolve().parents[2] / "reports" / "hw05" / "raw"
POLICY = RetryPolicy()
RATES = [0.0, 0.2, 0.5]
N_CALLS = 50
CALLS = [("search_trials", {"query": "Study", "limit": 5}),
         ("get_trial", {"trial_id": 5}),
         ("trial_stats", {"group_by": "status"})]


class ScriptedStore:
    """Fails the first `fail_times` calls (or hangs past the timeout), then works."""
    def __init__(self, store, fail_times=0, hang=False):
        self.store, self.left, self.hang = store, fail_times, hang

    def get(self, *a):
        if self.hang:
            time.sleep(POLICY.timeout_s + 0.5)
        if self.left > 0:
            self.left -= 1
            raise TransientError("simulated dropped DB connection")
        return self.store.get(*a)


def demo(base):
    log("=" * 70)
    log(f"Retry policy: max_attempts={POLICY.max_attempts}, timeout={POLICY.timeout_s}s per "
          f"attempt, backoff={POLICY.base_delay_s}s x2^n (cap {POLICY.max_delay_s}s)")
    cases = [("A) success on first attempt", ScriptedStore(base, 0)),
             ("B) fail once, then succeed on retry", ScriptedStore(base, 1)),
             ("C) fail on every attempt (timeouts)", ScriptedStore(base, 0, hang=True))]
    for title, store in cases:
        log("-" * 70); log(title)
        attempt_log = lambda n, status: log(f"   attempt {n}: {status}")
        try:
            row, used = call_with_retry(lambda: store.get(5), POLICY, on_attempt=attempt_log)
            log(f"   -> success after {used} attempt(s): trial {row['id']} '{row['trial_title']}'")
        except Exception as exc:
            log(f"   -> {type(exc).__name__}: {exc}")
        if title.startswith("C"):
            out = execute_tool("get_trial", {"trial_id": 5}, store=ResilientStore(store))
            log(f"   execute_tool returns a clean envelope instead of crashing:\n   {out}")


def p99(values):
    s = sorted(values)
    return s[max(0, math.ceil(0.99 * len(s)) - 1)]   # nearest-rank percentile


def fault_injection(base):
    rows, summary = [], []
    for rate in RATES:
        faulty = FaultyStore(base, rate, seed=VERIFY_SEED)
        store = ResilientStore(faulty, POLICY)
        lat, ok_count = [], 0
        for i in range(N_CALLS):
            name, inputs = CALLS[i % len(CALLS)]
            before = faulty.injected
            t0 = time.perf_counter()
            env = json.loads(execute_tool(name, inputs, store=store))
            ms = (time.perf_counter() - t0) * 1000
            injected = faulty.injected - before
            attempts = injected + 1 if env["ok"] else POLICY.max_attempts
            ok_count += env["ok"]
            lat.append(ms)
            rows.append({"failure_rate": rate, "call": i + 1, "tool": name, "ok": env["ok"],
                         "attempts": attempts, "injected_failures": injected,
                         "latency_ms": round(ms, 2), "error": env["error"] or ""})
        summary.append({"failure_rate": rate, "calls": N_CALLS,
                        "success_rate": ok_count / N_CALLS,
                        "mean_latency_ms": round(statistics.mean(lat), 2),
                        "p99_latency_ms": round(p99(lat), 2)})
    return rows, summary


def main():
    log("=" * 70)
    log(f"RUN: python run_part3.py   (HW5 Part 3, VERIFY_SEED={VERIFY_SEED}, data: s3209_rel)")
    base = core.SQLTrialStore()
    demo(base)
    rows, summary = fault_injection(base)
    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / "fault_injection_calls.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    (RAW / "fault_injection_summary.json").write_text(json.dumps(
        {"verify_seed": VERIFY_SEED, "policy": POLICY.__dict__, "results": summary}, indent=2))
    log("=" * 70)
    log(f"Fault injection: {N_CALLS} calls per rate, {len(rows)} calls total "
          f"(raw data: reports/hw05/raw/fault_injection_calls.csv)")
    log(f"{'Injected failure rate':<24}{'Success rate':<15}{'Mean latency (ms)':<20}p99 latency (ms)")
    for s in summary:
        log(f"{int(s['failure_rate']*100):>3}%{'':<20}{s['success_rate']*100:>6.1f}%{'':<8}"
              f"{s['mean_latency_ms']:>10.2f}{'':<10}{s['p99_latency_ms']:>10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
