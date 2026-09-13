import os
import re
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "reports" / "hw02" / "cases" / "schema_input.json"
RAW_DIR = BASE_DIR / "reports" / "hw02" / "raw"
LOG_FILE = BASE_DIR / "reports" / "hw02" / "CEILING_COMPARISON.txt"

RUNS_PER_CEILING = 20
CEILINGS = [2, 10]


def final_turn_count(output):
    values = re.findall(r'"turn_count"\s*:\s*(\d+)', output)
    return int(values[-1]) if values else None


def run_group(ceiling):
    results = []

    for number in range(1, RUNS_PER_CEILING + 1):
        command = [
            sys.executable,
            "agents_demo.py",
            "--input-file",
            str(INPUT_FILE),
            "--turn-ceiling",
            str(ceiling),
        ]

        clean_env = os.environ.copy()
        clean_env.pop("FORCE_PLANNER_INVALID", None)
        clean_env.pop("FORCE_REVIEW_ISSUE", None)

        start = time.perf_counter()

        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=clean_env,
        )

        latency_ms = (time.perf_counter() - start) * 1000
        output = result.stdout + "\n" + result.stderr

        raw_file = RAW_DIR / f"ceiling_{ceiling}_run_{number:03d}.txt"
        raw_file.write_text(output, encoding="utf-8")

        completed = (
            result.returncode == 0
            and "=== Final Graph State ===" in output
            and '"issues": []' in output
        )

        results.append(
            {
                "ceiling": ceiling,
                "run": number,
                "completed": completed,
                "turn_count": final_turn_count(output),
                "latency_ms": latency_ms,
                "return_code": result.returncode,
                "raw_file": str(raw_file),
            }
        )

        print(
            f"ceiling={ceiling} "
            f"run={number:02d}/{RUNS_PER_CEILING} "
            f"completed={completed} "
            f"turns={final_turn_count(output)} "
            f"latency_ms={latency_ms:.0f}"
        )

    return results


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    all_results = []

    for ceiling in CEILINGS:
        all_results.extend(run_group(ceiling))

    lines = [
        "DATA-260 Homework 2 Part 4",
        "Turn-ceiling comparison",
        f"Input: {INPUT_FILE}",
        "",
    ]

    for ceiling in CEILINGS:
        group = [r for r in all_results if r["ceiling"] == ceiling]
        completed = sum(r["completed"] for r in group)
        mean_latency = sum(r["latency_ms"] for r in group) / len(group)

        lines.append(f"TURN CEILING {ceiling}")
        lines.append(f"runs: {len(group)}")
        lines.append(f"completed: {completed}")
        lines.append(f"completion_rate: {completed / len(group):.4f}")
        lines.append(f"mean_latency_ms: {mean_latency:.2f}")
        lines.append("")

    LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("")
    print(f"Comparison complete. Log saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()