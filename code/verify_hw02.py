import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


CODE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = CODE_DIR.parent

REPORT_DIR = PROJECT_DIR / "reports" / "hw02"
INPUT_FILE = REPORT_DIR / "cases" / "schema_input.json"
VERIFICATION_FILE = REPORT_DIR / "verification.json"

PORT = 8509
MODEL = os.environ.get(
    "OLLAMA_MODEL",
    "qwen3:4b-instruct-2507-q4_K_M",
)

SEED = 3209
VERIFY_SEED = 263209


def run_command(command, cwd=None, timeout=180):
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def check_url(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except Exception:
        return None


def wait_for_url(url, timeout_seconds=20):
    end_time = time.time() + timeout_seconds

    while time.time() < end_time:
        status = check_url(url)

        if status is not None:
            return status

        time.sleep(0.5)

    return None


def validate_graph_output(output):
    if "=== Final Graph State ===" not in output:
        return False, "Final Graph State was not found."

    final_text = output.split("=== Final Graph State ===", 1)[1]

    try:
        final_state = json.loads(final_text)
    except json.JSONDecodeError as error:
        return False, f"Final graph state was not valid JSON: {error}"

    planner = final_state.get("planner_proposal", {})
    planner_data = planner.get("data", {})

    tags = planner_data.get("tags")
    summary = planner_data.get("summary")

    if not isinstance(tags, list):
        return False, "Planner tags were not returned as a list."

    if len(tags) != 3:
        return False, f"Planner returned {len(tags)} tags instead of 3."

    if not all(isinstance(tag, str) for tag in tags):
        return False, "At least one tag was not a string."

    if not all(3 <= len(tag) <= 30 for tag in tags):
        return False, "At least one tag was outside the 3-30 character range."

    if not isinstance(summary, str):
        return False, "Planner summary was not a string."

    if len(summary.split()) > 25:
        return False, "Planner summary contained more than 25 words."

    reviewer = final_state.get("reviewer_feedback", {})
    reviewer_data = reviewer.get("data", {})
    issues = reviewer_data.get("issues")

    if issues != []:
        return False, "Reviewer did not finish with an empty issues list."

    return True, "Graph returned valid Planner output and reviewer issues were empty."


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    checks = []
    server_process = None
    server_was_already_running = False

    commit_result = run_command(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_DIR,
    )

    commit_hash = commit_result.stdout.strip()

    tag_result = run_command(
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        cwd=PROJECT_DIR,
    )

    tag_name = tag_result.stdout.strip()

    checks.append(
        {
            "check": "Tagged commit exists",
            "pass": bool(commit_hash and tag_name),
            "details": tag_name if tag_name else "HEAD is not tagged.",
        }
    )

    checks.append(
        {
            "check": "Frozen input exists",
            "pass": INPUT_FILE.exists(),
            "details": str(INPUT_FILE),
        }
    )

    try:
        existing_status = check_url(
            f"http://127.0.0.1:{PORT}/docs"
        )

        if existing_status == 200:
            server_was_already_running = True
        else:
            server_process = subprocess.Popen(
                [sys.executable, "main.py"],
                cwd=CODE_DIR / "web_application",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        api_status = wait_for_url(
            f"http://127.0.0.1:{PORT}/docs"
        )

        checks.append(
            {
                "check": "FastAPI backend responds on PORT_BASE",
                "pass": api_status == 200,
                "details": f"HTTP status: {api_status}",
            }
        )

    except Exception as error:
        checks.append(
            {
                "check": "FastAPI backend responds on PORT_BASE",
                "pass": False,
                "details": str(error),
            }
        )

    finally:
        if server_process is not None:
            server_process.terminate()

            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()

    graph_start = time.perf_counter()

    try:
        graph_result = run_command(
            [
                sys.executable,
                "agents_demo.py",
                "--input-file",
                str(INPUT_FILE),
                "--turn-ceiling",
                "10",
            ],
            cwd=CODE_DIR,
            timeout=180,
        )

        graph_latency_ms = (time.perf_counter() - graph_start) * 1000
        graph_output = graph_result.stdout + "\n" + graph_result.stderr

        graph_pass, graph_details = validate_graph_output(graph_output)

        checks.append(
            {
                "check": "LangGraph smoke test finishes with valid output",
                "pass": graph_result.returncode == 0 and graph_pass,
                "details": (
                    f"{graph_details}; "
                    f"latency_ms={graph_latency_ms:.2f}; "
                    f"return_code={graph_result.returncode}"
                ),
            }
        )

    except subprocess.TimeoutExpired:
        checks.append(
            {
                "check": "LangGraph smoke test finishes with valid output",
                "pass": False,
                "details": "Graph exceeded the 180-second timeout.",
            }
        )

    all_passed = all(item["pass"] for item in checks)

    verification = {
        "homework": "DATA-260 Homework 2",
        "sid4": "3209",
        "commit_hash": commit_hash,
        "tag": tag_name,
        "model": MODEL,
        "configuration": {
            "port_base": PORT,
            "input_file": str(INPUT_FILE),
            "turn_ceiling": 10,
            "forced_test_variables_cleared": (
                os.environ.get("FORCE_PLANNER_INVALID") != "1"
                and os.environ.get("FORCE_REVIEW_ISSUE") != "1"
            ),
        },
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "overall_pass": all_passed,
    }

    VERIFICATION_FILE.write_text(
        json.dumps(verification, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(verification, indent=2))
    print("")
    print(f"Verification file written to: {VERIFICATION_FILE}")

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()