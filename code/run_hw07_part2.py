"""HW7 Part 2 runner.

  python code/run_hw07_part2.py demo [--task A|B|C|E]  # tasks A, B, C + nonexistent id (T=0)
  python code/run_hw07_part2.py reliability -n 21    # >= 20 attempts over the 3 fixed cases

Raw data: reports/hw07/raw/part2_reliability.csv and part2_reliability_summary.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code" / "mcp_servers"))
os.chdir(ROOT)

from agent_loop import FAILURE_TYPES, AdapterModel, run_agent  # noqa: E402
from tool_gateway import execute_tool  # noqa: E402

CASES = json.loads((ROOT / "reports/hw07/cases/part2_tasks.json").read_text())
RAW = ROOT / "reports/hw07/raw"
VERIFY_SEED = 263209
RELIABILITY_TEMPERATURE = 0.7


def chain_complete(tool_calls: list[dict], expected: list[str]) -> bool:
    """Return True when the successful tool calls contain the expected chain in order."""
    done = [c["name"] for c in tool_calls if c["ok"]]
    i = 0
    for name in done:
        if i < len(expected) and name == expected[i]:
            i += 1
    return i == len(expected)


def slot_stats(emissions: list[dict]) -> tuple[int, int, int]:
    """Return (tool slots, well-formed on first try, well-formed after repair).

    A slot is one request for the next action; it ends with a valid tool call, a valid
    final answer, or the repair limit. Slots that start with a valid final answer are not
    tool slots. A slot counts as well-formed after repair when its last reply is valid."""
    slots, current = [], []
    for e in emissions:
        current.append(e)
        if e["well_formed"]:
            slots.append(current)
            current = []
    if current:
        slots.append(current)
    tool_slots = [s for s in slots if not (s[0]["well_formed"] and s[0]["kind"] == "final")]
    first = sum(1 for s in tool_slots if s[0]["well_formed"] and s[0]["kind"] == "tool")
    after = sum(1 for s in tool_slots if s[-1]["well_formed"])
    return len(tool_slots), first, after


def header(title: str) -> None:
    print(f"\n================ HW7 Part 2: {title} ================")
    print("Run by: Ani Taraiya (s3209)   model: llama3.1:8b via src/model_client.py")


def demo(only: str | None = None) -> None:
    model = AdapterModel(temperature=0.0)
    for key, task in CASES["tasks"].items():
        if only and only != key:
            continue
        header(f"Task {key} - {task['title']}")
        res = run_agent(task["prompt"], model=model)
        ok = chain_complete(res.tool_calls, task["expected_chain"])
        print(f"  expected chain {task['expected_chain']} -> {'complete' if ok else 'INCOMPLETE'}")
    if only and only != "E":
        return
    err = CASES["error_case"]
    header("Error recovery - nonexistent id")
    print(f"  execute_tool('get_trial', {{'trial_id': {err['trial_id']}}}) ->")
    print("   ", execute_tool("get_trial", {"trial_id": err["trial_id"]}))
    res = run_agent(err["prompt"], model=model)
    print(f"  agent finished without crashing: stop={res.stop_reason}")


def reliability(n: int) -> None:
    keys = list(CASES["tasks"])
    rows = []
    header(f"Reliability - {n} attempts, temperature {RELIABILITY_TEMPERATURE}")
    for i in range(n):
        key = keys[i % len(keys)]
        task = CASES["tasks"][key]
        seed = VERIFY_SEED + i
        res = run_agent(task["prompt"], model=AdapterModel(RELIABILITY_TEMPERATURE, seed),
                        log=lambda s: None)
        slots, first, after = slot_stats(res.emissions)
        failures = [e["failure_type"] for e in res.emissions if e["failure_type"]]
        complete = chain_complete(res.tool_calls, task["expected_chain"])
        if res.stop_reason == "final_answer" and not complete:
            failures.append("lost_multi_step_chain")
        rows.append({"attempt": i + 1, "task": key, "temperature": RELIABILITY_TEMPERATURE,
                     "seed": seed, "tool_slots": slots, "well_formed_first_try": first,
                     "well_formed_after_repair": after, "repairs": res.repairs,
                     "tool_calls": res.total_tool_calls, "chain_complete": complete,
                     "stop_reason": res.stop_reason, "failure_types": ";".join(failures),
                     "tokens": res.input_tokens + res.output_tokens,
                     "latency_ms": res.latency_ms, "run_id": res.run_id})
        print(f"  attempt {i + 1:>2} task {key}: calls={res.total_tool_calls} "
              f"first-try {first}/{slots}, after-repair {after}/{slots}, "
              f"chain={'ok' if complete else 'LOST'}, stop={res.stop_reason}, "
              f"failures={failures or '-'}")

    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / "part2_reliability.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    total = sum(r["tool_slots"] for r in rows)
    first = sum(r["well_formed_first_try"] for r in rows)
    after = sum(r["well_formed_after_repair"] for r in rows)
    counts = Counter(f for r in rows for f in r["failure_types"].split(";") if f)
    summary = {"attempts": n, "temperature": RELIABILITY_TEMPERATURE,
               "seeds": f"{VERIFY_SEED}..{VERIFY_SEED + n - 1}", "model": "llama3.1:8b",
               "tool_call_slots": total,
               "well_formed_before_repair": first,
               "well_formed_after_repair": after,
               "rate_before_repair": round(first / total, 3) if total else None,
               "rate_after_repair": round(after / total, 3) if total else None,
               "chains_complete": sum(r["chain_complete"] for r in rows),
               "failures_by_type": {t: counts.get(t, 0) for t in FAILURE_TYPES}}
    (RAW / "part2_reliability_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n  Summary")
    print(f"  tool-call slots: {total}")
    print(f"  well-formed before repair: {first}/{total} = {summary['rate_before_repair']:.1%}")
    print(f"  well-formed after repair:  {after}/{total} = {summary['rate_after_repair']:.1%}")
    print(f"  multi-step chains complete: {summary['chains_complete']}/{n}")
    for t in FAILURE_TYPES:
        print(f"  {t:<24} {counts.get(t, 0)}")
    print("  raw: reports/hw07/raw/part2_reliability.csv, part2_reliability_summary.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["demo", "reliability"])
    ap.add_argument("-n", type=int, default=21)
    ap.add_argument("--task", choices=["A", "B", "C", "E"])
    a = ap.parse_args()
    demo(a.task) if a.mode == "demo" else reliability(a.n)
