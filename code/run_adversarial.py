import os
import re
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "reports" / "hw02" / "cases" / "adversarial_input.json"
RAW_DIR = BASE_DIR / "reports" / "hw02" / "raw"
LOG_FILE = BASE_DIR / "reports" / "hw02" / "ADVERSARIAL_LOG.txt"

RUN_COUNT = 5
TURN_CEILING = 10


def get_turn_count(output):
    values = re.findall(r'"turn_count"\s*:\s*(\d+)', output)
    return int(values[-1]) if values else None


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "DATA-260 Homework 2 Part 4",
        "Adversarial-input experiment",
        f"Input: {INPUT_FILE}",
        f"Turn ceiling: {TURN_CEILING}",
        "",
    ]

    ceiling_count = 0

    for number in range(1, RUN_COUNT + 1):
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

        raw_file = RAW_DIR / f"adversarial_run_{number:03d}.txt"
        raw_file.write_text(output, encoding="utf-8")

        turn_count = get_turn_count(output)
        reached_ceiling = turn_count == TURN_CEILING
        if reached_ceiling:
            ceiling_count += 1

        lines.append(
            f"run={number:03d} "
            f"turn_count={turn_count} "
            f"reached_ceiling={reached_ceiling} "
            f"latency_ms={latency_ms:.2f} "
            f"return_code={result.returncode} "
            f"raw_file={raw_file}"
        )

        print(
            f"Run {number}/{RUN_COUNT}: "
            f"turn_count={turn_count}; "
            f"reached_ceiling={reached_ceiling}; "
            f"latency_ms={latency_ms:.0f}"
        )

    lines.extend(
        [
            "",
            "SUMMARY",
            f"runs_reaching_ceiling: {ceiling_count}/{RUN_COUNT}",
            f"ceiling_rate: {ceiling_count / RUN_COUNT:.4f}",
        ]
    )

    LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Log saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()