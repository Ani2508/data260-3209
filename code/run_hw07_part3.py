"""HW7 Part 3 runner - original loop vs bounded Reflexion on the 3 fixed tasks.

  python code/run_hw07_part3.py compare -n 5     # n runs per task for each loop (same seeds)
  python code/run_hw07_part3.py show             # print one stored failed-then-retried reflection

Raw data: reports/hw07/raw/part3_comparison.csv, part3_summary.json, part3_reflections.jsonl.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code" / "mcp_servers"))
os.chdir(ROOT)

from agent_loop import AdapterModel, run_agent  # noqa: E402
from reflexion import (  # noqa: E402
    REFLECTIONS_PATH,
    ground_truth,
    oracle,
    run_reflexion,
    task_list,
    to_dict,
    unsupported_claims,
    verify,
)

RAW = ROOT / "reports/hw07/raw"
AGENT_LOG = RAW / "part3_agent_runs.jsonl"
SEED0 = 263209 + 100
TEMPERATURE = 0.7


def header(title: str) -> None:
    print(f"\n================ HW7 Part 3: {title} ================")
    print("Run by: Ani Taraiya (s3209)   model: llama3.1:8b via src/model_client.py")


def compare(n: int) -> None:
    tasks, truth = task_list(), ground_truth()
    header(f"original vs Reflexion - {n} runs per task, temperature {TEMPERATURE}")
    rows = []
    for key, task in tasks.items():
        for i in range(n):
            seed = SEED0 + i
            res = run_agent(task["prompt"], model=AdapterModel(TEMPERATURE, seed),
                            log=lambda s: None, log_path=AGENT_LOG)
            v = verify(key, res, truth)
            unsup = unsupported_claims(res)
            rows.append({"loop": "original", "task": key, "seed": seed,
                         "success": v["passed"], "attempts": 1, "retries": 0,
                         "tool_calls": res.total_tool_calls,
                         "tokens": res.input_tokens + res.output_tokens,
                         "latency_ms": res.latency_ms, "unsupported_claims": len(unsup),
                         "false_rejections": int(not v["passed"] and oracle(key, res, truth)
                                                 and not unsup),
                         "stop_reason": res.stop_reason, "answer": res.answer})
            print(f"  original  task {key} seed {seed}: "
                  f"{'PASS' if v['passed'] else 'FAIL'}  calls={res.total_tool_calls}")

            print(f"  reflexion task {key} seed {seed}:")
            rr = run_reflexion(key, task["prompt"], truth, model=AdapterModel(TEMPERATURE, seed),
                               agent_log_path=AGENT_LOG,
                               log=lambda s: print("   " + s) if "verifier" in s
                               or "reflection" in s or "reflexion stop" in s else None)
            fin = rr.final
            rows.append({"loop": "reflexion", "task": key, "seed": seed,
                         "success": rr.stop_reason == "success",
                         "attempts": len(rr.attempts), "retries": rr.retries,
                         "tool_calls": rr.tool_calls, "tokens": rr.tokens,
                         "latency_ms": rr.latency_ms,
                         "unsupported_claims": len(fin["unsupported"]),
                         "false_rejections": sum(int(not a["verifier"]["passed"]
                                                     and a["oracle_pass"] and not a["unsupported"])
                                                 for a in rr.attempts),
                         "stop_reason": rr.stop_reason, "answer": fin["answer"]})
            with open(RAW / "part3_reflexion_runs.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"seed": seed, **to_dict(rr)}, default=str) + "\n")

    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / "part3_comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    def agg(loop: str) -> dict:
        r = [x for x in rows if x["loop"] == loop]
        return {"runs": len(r),
                "task_success": f"{sum(x['success'] for x in r)}/{len(r)}",
                "unsupported_claims": sum(x["unsupported_claims"] for x in r),
                "retry_rate": f"{sum(x['retries'] > 0 for x in r)}/{len(r)}",
                "tool_calls_mean": round(mean(x["tool_calls"] for x in r), 2),
                "tokens_mean": round(mean(x["tokens"] for x in r)),
                "latency_ms_mean": round(mean(x["latency_ms"] for x in r)),
                "verifier_false_rejections": sum(x["false_rejections"] for x in r)}

    summary = {"temperature": TEMPERATURE, "seeds": f"{SEED0}..{SEED0 + n - 1}",
               "runs_per_task": n, "original": agg("original"), "reflexion": agg("reflexion")}
    (RAW / "part3_summary.json").write_text(json.dumps(summary, indent=2))
    o, r = summary["original"], summary["reflexion"]
    print("\n  Metric                     Original loop   Reflexion loop")
    for label, key in [("Task success", "task_success"),
                       ("Unsupported claims", "unsupported_claims"),
                       ("Retry rate", "retry_rate"), ("Tool calls (mean)", "tool_calls_mean"),
                       ("Tokens (mean)", "tokens_mean"), ("Latency ms (mean)", "latency_ms_mean"),
                       ("Verifier false rejections", "verifier_false_rejections")]:
        print(f"  {label:<26} {str(o[key]):<15} {r[key]}")
    print("  raw: reports/hw07/raw/part3_comparison.csv, part3_summary.json, "
          "part3_reflections.jsonl")


def show() -> None:
    header("stored reflection (failed, then retried)")
    if not REFLECTIONS_PATH.exists():
        print("  no reflections stored yet - run: make hw07-part3")
        return
    rows = [json.loads(x) for x in REFLECTIONS_PATH.read_text().splitlines() if x]
    runs = [json.loads(x) for x in (RAW / "part3_reflexion_runs.jsonl").read_text().splitlines()]
    fixed = {x["run_id"] for x in runs if x["stop_reason"] == "success" and x["attempts"][1:]}
    rec = next((r for r in rows if r["run_id"] in fixed), rows[-1])
    ev = rec["evidence"]
    print(f"  user_id={rec['user_id']}  run_id={rec['run_id']}  task={rec['task']}  "
          f"after attempt {rec['after_attempt']}")
    print("  EVIDENCE")
    for a in ev["failed_assertions"]:
        print(f"    assertion FAILED: {a}")
    for c in ev["tool_calls"]:
        print(f"    tool: {c['name']} {json.dumps(c['arguments'])} -> {c['observation'][:110]}")
    for e in ev.get("invalid_replies", []):
        print(f"    invalid reply: {e[:120]}")
    print(f"    final answer: {ev['final_answer'][:160]}")
    print("  REFLECTION")
    print(f"    failure:  {rec['failure']}")
    print(f"    strategy: {rec['strategy']}")
    run = next((x for x in runs if x["run_id"] == rec["run_id"]), None)
    if run:
        for a in run["attempts"]:
            verdict = "PASS" if a["verifier"]["passed"] else "FAIL"
            print(f"  attempt {a['attempt']}: verifier {verdict} | {a['answer'][:120]}")
        print(f"  stop reason: {run['stop_reason']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["compare", "show"])
    ap.add_argument("-n", type=int, default=5)
    a = ap.parse_args()
    compare(a.n) if a.mode == "compare" else show()
