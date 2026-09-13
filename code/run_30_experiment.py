import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

INPUT_FILE = PROJECT_DIR / "reports" / "hw02" / "cases" / "schema_input.json"
RAW_DIR = PROJECT_DIR / "reports" / "hw02" / "raw"
LOG_FILE = PROJECT_DIR / "reports" / "hw02" / "RUN_LOG.txt"

RUN_COUNT = 30
TURN_CEILING = 10


def classify_run(output, return_code):
    if return_code != 0 or "=== Final Graph State ===" not in output:
        return "abandoned at ceiling"

    validation_failures = (
        output.count("--- Planner validation failed ---")
        + output.count("--- TEST: Forced Planner validation failure ---")
    )

    if validation_failures == 0:
        return "valid first attempt"

    if validation_failures == 1:
        return "valid after one retry"

    return "valid after two or more retries"


def get_final_turn_count(output):
    matches = re.findall(r'"turn_count"\s*:\s*(\d+)', output)
    return int(matches[-1]) if matches else None


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    experiment_started = datetime.now(timezone.utc).isoformat()

    log_lines = [
        "DATA-260 Homework 2 Part 4",
        "Experiment: 30 runs on one frozen input",
        f"Experiment started UTC: {experiment_started}",
        f"Input: {INPUT_FILE}",
        f"Turn ceiling: {TURN_CEILING}",
        f"Model: qwen3:4b-instruct-2507-q4_K_M",
        "",
    ]

    counts = {
        "valid first attempt": 0,
        "valid after one retry": 0,
        "valid after two or more retries": 0,
        "abandoned at ceiling": 0,
    }

    for run_number in range(1, RUN_COUNT + 1):
        command = [
            sys.executable,
            "agents_demo.py",
            "--input-file",
            str(INPUT_FILE),
            "--turn-ceiling",
            str(TURN_CEILING),
        ]

        clean_env = os.environ.copy()
        clean_env.pop("FORCE_PLANNER_INVALID", None)
        clean_env.pop("FORCE_REVIEW_ISSUE", None)

        started_at = datetime.now(timezone.utc).isoformat()
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
        finished_at = datetime.now(timezone.utc).isoformat()

        output = result.stdout + "\n" + result.stderr

        raw_file = RAW_DIR / f"run_{run_number:03d}.txt"
        raw_file.write_text(output, encoding="utf-8")

        category = classify_run(output, result.returncode)
        turn_count = get_final_turn_count(output)
        counts[category] += 1

        log_lines.append(
            f"RUN {run_number:03d}"
        )
        log_lines.append(f"started_at_utc={started_at}")
        log_lines.append(f"finished_at_utc={finished_at}")
        log_lines.append(f"category={category}")
        log_lines.append(f"turn_count={turn_count}")
        log_lines.append(f"latency_ms={latency_ms:.2f}")
        log_lines.append(f"return_code={result.returncode}")
        log_lines.append(f"raw_file={raw_file}")
        log_lines.append("----- REAL CONSOLE OUTPUT -----")
        log_lines.append(output.rstrip())
        log_lines.append("----- END CONSOLE OUTPUT -----")
        log_lines.append("")

        print(
            f"Run {run_number:02d}/{RUN_COUNT}: "
            f"{category}; turns={turn_count}; latency={latency_ms:.0f} ms"
        )

    experiment_finished = datetime.now(timezone.utc).isoformat()

    log_lines.extend(
        [
            "SUMMARY",
            f"Experiment finished UTC: {experiment_finished}",
            f"valid first attempt: {counts['valid first attempt']}",
            f"valid after one retry: {counts['valid after one retry']}",
            f"valid after two or more retries: "
            f"{counts['valid after two or more retries']}",
            f"abandoned at ceiling: {counts['abandoned at ceiling']}",
        ]
    )

    LOG_FILE.write_text(
        "\n".join(log_lines) + "\n",
        encoding="utf-8",
    )

    print("")
    print("Experiment complete.")
    print(f"Log saved to: {LOG_FILE}")
    print(f"Raw outputs saved to: {RAW_DIR}")


if __name__ == "__main__":
    main()