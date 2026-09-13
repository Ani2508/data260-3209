import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CODE_DIR = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"

sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(CODE_DIR))

from agents_demo import (  # noqa: E402
    AgentState,
    PlannerOutput,
    ModelClient,
    build_graph,
)


DEFAULT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"


def classify_result(final_state, ceiling):
    proposal = final_state.get("planner_proposal", {})
    attempts = final_state.get("planner_attempts", 0)
    turn_count = final_state.get("turn_count", 0)

    try:
        PlannerOutput.model_validate(proposal["data"])
        valid = True
    except Exception as error:
        valid = False
        validation_error = str(error)

    if valid and attempts == 1:
        outcome = "valid first attempt"
    elif valid and attempts == 2:
        outcome = "valid after one retry"
    elif valid and attempts >= 3:
        outcome = "valid after two or more retries"
    elif turn_count >= ceiling:
        outcome = "abandoned at the ceiling"
    else:
        outcome = "abandoned before the ceiling"

    return outcome, valid, validation_error if not valid else ""


def run_one(graph, client, case, ceiling):
    initial_state: AgentState = {
        "title": case["title"],
        "content": case["content"],
        "email": case.get("email", "student@example.com"),
        "strict": case.get("strict", True),
        "task": (
            f'Given title "{case["title"]}" and content '
            f'"{case["content"]}", produce exactly 3 topical tags '
            "and a summary of no more than 25 words."
        ),
        "llm": client,
        "planner_proposal": {},
        "reviewer_feedback": {},
        "turn_count": 0,
        "turn_ceiling": ceiling,
        "planner_attempts": 0,
    }

    started_at = datetime.now(timezone.utc).isoformat()
    start_time = time.perf_counter()

    final_state = initial_state

    for state in graph.stream(
        initial_state,
        stream_mode="values",
    ):
        final_state = state

    latency_ms = round(
        (time.perf_counter() - start_time) * 1000,
        2,
    )

    outcome, valid, validation_error = classify_result(
        final_state,
        ceiling,
    )

    return {
        "started_at": started_at,
        "ceiling": ceiling,
        "planner_attempts": final_state.get(
            "planner_attempts",
            0,
        ),
        "turn_count": final_state.get(
            "turn_count",
            0,
        ),
        "outcome": outcome,
        "valid": valid,
        "latency_ms": latency_ms,
        "validation_error": validation_error,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--case",
        default=str(
            REPO_ROOT
            / "reports"
            / "hw02"
            / "cases"
            / "schema_input.json"
        ),
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=30,
    )

    parser.add_argument(
        "--ceiling",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
    )

    parser.add_argument(
        "--output",
        default=str(
            REPO_ROOT
            / "reports"
            / "hw02"
            / "raw"
            / "schema_runs.csv"
        ),
    )

    args = parser.parse_args()

    case_path = Path(args.case)
    output_path = Path(args.output)

    case = json.loads(
        case_path.read_text(encoding="utf-8")
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = ModelClient(
        model=args.model,
        temperature=args.temperature,
    )

    graph = build_graph()

    rows = []

    print(f"Model: {args.model}")
    print(f"Temperature: {args.temperature}")
    print(f"Turn ceiling: {args.ceiling}")
    print(f"Runs: {args.runs}")
    print("")

    for run_number in range(1, args.runs + 1):
        print(f"Starting run {run_number}/{args.runs}")

        result = run_one(
            graph=graph,
            client=client,
            case=case,
            ceiling=args.ceiling,
        )

        result["run"] = run_number
        result["model"] = args.model
        result["temperature"] = args.temperature

        rows.append(result)

        print(
            f"Run {run_number}: "
            f"{result['outcome']} | "
            f"{result['latency_ms']} ms"
        )

    fieldnames = [
        "run",
        "started_at",
        "model",
        "temperature",
        "ceiling",
        "planner_attempts",
        "turn_count",
        "outcome",
        "valid",
        "latency_ms",
        "validation_error",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)

    print("")
    print(f"Saved raw results to: {output_path}")


if __name__ == "__main__":
    main()