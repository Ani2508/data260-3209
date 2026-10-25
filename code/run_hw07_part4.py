"""HW7 Part 4 runner - run the bike-share agent on a scenario and save the evidence.

  python code/run_hw07_part4.py A        # membership-wins scenario
  python code/run_hw07_part4.py B        # pay-per-use-wins scenario

Saves reports/hw07/raw/part4_scenario{X}/: pricing_snapshot.txt (exact page text),
pricing_snapshot.json (url, access time, SHA-256), result.json (decision, costs, timeline).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from bikeshare.agent import run_bike_agent, save_evidence  # noqa: E402

PRICING_URL = "https://citibikenyc.com/pricing"
CASES = ROOT / "reports/hw07/cases"
RAW = ROOT / "reports/hw07/raw"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", choices=["A", "B"])
    ap.add_argument("--url", default=PRICING_URL)
    a = ap.parse_args()
    csv_path = CASES / f"part4_scenario{a.scenario}_trips.csv"
    print(f"\n================ HW7 Part 4: scenario {a.scenario} ================")
    print("Run by: Ani Taraiya (s3209)   framework: LangChain create_agent + qwen3:8b (Ollama)")
    print(f"  csv: {csv_path.relative_to(ROOT)}   pricing: {a.url}")
    r = run_bike_agent(csv_path, a.url)
    for ev in r["timeline"]:
        if ev["type"] == "tool_call":
            print(f"  [{ev['t_ms']:>6} ms] CALL {ev['tool']} {json.dumps(ev['args'])[:150]}")
        else:
            print(f"  [{ev['t_ms']:>6} ms] OBS  {ev['tool']} {ev['content'][:150]}")
    f = r["final"] or {}
    print(f"  DECISION: {r['decision']}")
    for k in ("pay_per_use_total", "membership_total", "membership_fees",
              "member_residual_charges", "break_even_rides_per_rider_month",
              "actual_rides_per_rider_month"):
        print(f"    {k}: {f.get(k)}")
    print(f"  justification: {f.get('justification')}")
    print(f"  weekly rows: {len(r['weekly'])}   assumptions: {f.get('assumptions')}")
    snap = save_evidence(r, RAW / f"part4_scenario{a.scenario}")
    print(f"  snapshot: {snap.get('url')} at {snap.get('accessed_at')} sha256 {snap.get('sha256')}")
    m = r["metrics"]
    print(f"  steps: {m['steps']} | total time: {m['total_ms']} ms | stop: {m['stop_reason']}")


if __name__ == "__main__":
    main()
