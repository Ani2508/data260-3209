"""HW8 Part 1 demo: CREATE_TRIAL -> GET_TRIAL through Kafka, with the full message flow.

Needs the Kafka stack running (make hw08-up). Run:  python code/homework_demo.py [--errors]
Worker lines are read from the worker container log (docker logs) for each correlation_id.
"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "kafka_service"))

from config import PREFIX, REQUEST_TOPIC, RESPONSE_TOPIC, RUN_BY  # noqa: E402
from kafka_client import TrialKafkaClient  # noqa: E402

WORKER_CONTAINER = f"{PREFIX}_trial_worker"
TRIAL = {
    "trialTitle": "Phase II Study of Drug X in Type 2 Diabetes",
    "sponsor": "Stanford Clinical Research Center",
    "email": "coordinator@stanford-crc.org",
    "content": "Randomized trial of a new oral medication for adults with type 2 "
               "diabetes, measuring HbA1c change over 24 weeks.",
    "status": "Recruiting",
    "terms": True,
}


def step(n: int, text: str):
    print(f"\n[Step {n}] {text}")


def worker_lines(cid: str) -> list[str]:
    """Worker log lines for one correlation_id (read from the worker container)."""
    time.sleep(0.3)
    try:
        out = subprocess.run(["docker", "logs", WORKER_CONTAINER], capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ["(docker logs not available)"]
    return [ln for ln in (out.stdout + out.stderr).splitlines() if cid in ln]


def show(lines: list[str], tag: str):
    for line in lines:
        if tag in line:
            print("   ", line)


def error_cases(client: TrialKafkaClient):
    """Unknown trial_id, unknown operation, invalid data: clean errors, same correlation_id."""
    cases = [("GET_TRIAL", {"trial_id": "00000000-0000-0000-0000-000000000000"}),
             ("DELETE_TRIAL", {"trial_id": "x"}),
             ("CREATE_TRIAL", {**TRIAL, "email": "not-an-email", "content": "too short"})]
    for op, data in cases:
        cid = client.new_correlation_id()
        print(f"\n---- {op} (expected error) ----")
        response = client.request(op, data, correlation_id=cid)
        print(json.dumps(response, indent=2))
        print(f"    correlation_id preserved: {response.get('correlation_id') == cid}")


def main():
    print(f"HW8 Part 1 demo   Run by: {RUN_BY} ({PREFIX})   "
          f"{datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"topics: {REQUEST_TOPIC} -> worker -> {RESPONSE_TOPIC}")
    client = TrialKafkaClient(role="client")
    if "--errors" in sys.argv:
        error_cases(client)
        client.close()
        return

    print("\n================ CREATE_TRIAL ================")
    cid = client.new_correlation_id()
    step(1, f"correlation_id created: {cid}")
    step(2, f"CREATE_TRIAL request sent to {REQUEST_TOPIC}")
    message = client.send("CREATE_TRIAL", TRIAL, correlation_id=cid)
    step(3, "message on the request topic")
    print(json.dumps(message, indent=2))
    created = client.wait(message)
    lines = worker_lines(cid)
    step(4, "worker received and processed the request")
    show(lines, "RECEIVED")
    show(lines, "PROCESSED")
    step(5, f"worker sent the response to {RESPONSE_TOPIC}")
    show(lines, "REPLIED")
    step(6, "response received by the client")
    print(json.dumps(created, indent=2))
    if not created.get("success"):
        sys.exit("CREATE_TRIAL failed")
    trial_id = created["trial_id"]
    step(7, f"trial_id extracted: {trial_id}")

    print("\n================ GET_TRIAL ================")
    get_cid = client.new_correlation_id()
    step(8, f"GET_TRIAL request sent with trial_id {trial_id} (correlation_id {get_cid})")
    got = client.request("GET_TRIAL", {"trial_id": trial_id}, correlation_id=get_cid)
    step(9, "GET_TRIAL sequence: send -> receive -> process -> reply -> client response")
    print(f"    SEND      client -> {REQUEST_TOPIC} cid={get_cid}")
    show(worker_lines(get_cid), "")
    print(f"    RESPONSE  {RESPONSE_TOPIC} -> client cid={got.get('correlation_id')} "
          f"success={got.get('success')}")

    step(10, "retrieved trial")
    print(json.dumps(got.get("trial"), indent=2))
    same = bool(got.get("success")) and {k: got["trial"][k] for k in TRIAL} == TRIAL
    print(f"    trial data matches what was created: {same}")
    print(f"    CREATE correlation_id preserved: {created['correlation_id'] == cid}")
    print(f"    GET    correlation_id preserved: {got.get('correlation_id') == get_cid}")
    client.close()


if __name__ == "__main__":
    main()
