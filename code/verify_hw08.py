"""HW8 smoke test -> reports/hw08/verification.json   (run: make verify-hw08)

Needs the Kafka stack (make hw08-up), the HW8 topics (make hw08-topics, make hw08-topic-dlq)
and Ollama with llama3.1:8b. Stop any Planner/Writer/Reviewer terminals first: this script
starts its own agents and stops them at the end. It never edits application code; it only
sends test messages to the s3209_* topics.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "code" / "kafka_agents"
for sub in ("code/kafka_service", "code/kafka_agents"):
    sys.path.insert(0, str(ROOT / sub))

from kafka import KafkaConsumer, KafkaProducer, TopicPartition  # noqa: E402

from common import BOOTSTRAP, DRAFTS, FINAL, INBOX, MODEL, TASKS  # noqa: E402
from config import PORT_BASE, PREFIX, REQUEST_TOPIC, RESPONSE_TOPIC  # noqa: E402
from kafka_client import TrialKafkaClient  # noqa: E402
from reliable import DEAD_LETTER  # noqa: E402

SID4, SEED, VERIFY_SEED = 3209, 3209, 263209
OUT = ROOT / "reports" / "hw08" / "verification.json"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
TRIAL = {"trialTitle": "Verify Study of Drug Z in Hypertension",
         "sponsor": "SJSU Verify Lab", "email": "verify@sjsu-lab.org",
         "content": "Smoke-test trial used by verify_hw08 to check the Kafka round trip.",
         "status": "Recruiting", "terms": True}
PLAN = ["List eligibility", "Explain risks", "Suggest asking a doctor"]
state: dict = {}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                          cwd=ROOT).stdout.strip()


def check(part: str, name: str, fn) -> dict:
    t0 = time.perf_counter()
    try:
        ok, detail = fn()
    except Exception as exc:
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    secs = round(time.perf_counter() - t0, 1)
    print(f"[{'PASS' if ok else 'FAIL'}] {part} {name} - {detail} ({secs}s)", flush=True)
    return {"part": part, "check": name, "pass": bool(ok), "detail": str(detail)[:300],
            "seconds": secs}


class Agent:
    """One agent process; output kept so we can wait for a log line."""

    def __init__(self, script: str, *args: str):
        self.proc = subprocess.Popen([sys.executable, "-u", script, *args], cwd=AGENTS,
                                     text=True, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
        self.lines: list[str] = []
        threading.Thread(target=lambda: self.lines.extend(self.proc.stdout),
                         daemon=True).start()

    def wait(self, text: str, timeout: float = 90) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if any(text in ln for ln in list(self.lines)):
                return True
            time.sleep(0.3)
        return False

    def stop(self):
        self.proc.terminate()
        self.proc.wait(timeout=10)


def topic_info() -> dict:
    c = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None)
    info = {t: len(c.partitions_for_topic(t) or []) for t in c.topics() if t.startswith(PREFIX)}
    c.close()
    return info


def end_offsets(topic: str) -> dict:
    c = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None)
    tps = [TopicPartition(topic, p) for p in c.partitions_for_topic(topic)]
    ends = c.end_offsets(tps)
    c.close()
    return ends


def read_since(topic: str, start: dict, idle: float = 3) -> list[dict]:
    c = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None, enable_auto_commit=False,
                      consumer_timeout_ms=int(idle * 1000))
    c.assign(list(start))
    for tp, off in start.items():
        c.seek(tp, off)
    msgs = [json.loads(r.value) for r in c]
    c.close()
    return msgs


def wait_for(topic: str, start: dict, cid: str, timeout: float = 120) -> list[dict]:
    end = time.time() + timeout
    while time.time() < end:
        hits = [m for m in read_since(topic, start, idle=2) if m.get("correlation_id") == cid]
        if hits:
            return hits
    return []


def producer() -> KafkaProducer:
    state.setdefault("producer", KafkaProducer(
        bootstrap_servers=BOOTSTRAP, acks="all", key_serializer=str.encode,
        value_serializer=lambda v: json.dumps(v).encode()))
    return state["producer"]


# ---------------- Part 1 ----------------
def p1_containers():
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], capture_output=True,
                         text=True).stdout.split()
    need = [f"{PREFIX}_kafka", f"{PREFIX}_trial_worker", f"{PREFIX}_trial_api"]
    missing = [n for n in need if n not in out]
    return not missing, f"running: {[n for n in need if n in out]}" + (
        f" missing: {missing}" if missing else "")


def p1_topics():
    info = topic_info()
    state["topics"] = info
    ok = REQUEST_TOPIC in info and RESPONSE_TOPIC in info
    return ok, f"{REQUEST_TOPIC}={info.get(REQUEST_TOPIC)} {RESPONSE_TOPIC}=" \
               f"{info.get(RESPONSE_TOPIC)} partitions"


def p1_create():
    client = state.setdefault("client", TrialKafkaClient(role="verify"))
    cid = str(uuid.uuid4())
    r = client.request("CREATE_TRIAL", TRIAL, correlation_id=cid)
    state["trial_id"] = r.get("trial_id")
    ok = r.get("success") is True and r.get("correlation_id") == cid \
        and bool(UUID_RE.match(str(r.get("trial_id"))))
    return ok, f"success={r.get('success')} uuid trial_id={state['trial_id']} cid kept=" \
               f"{r.get('correlation_id') == cid}"


def p1_get():
    cid = str(uuid.uuid4())
    r = state["client"].request("GET_TRIAL", {"trial_id": state["trial_id"]}, correlation_id=cid)
    trial = r.get("trial") or {}
    same = all(trial.get(k) == v for k, v in TRIAL.items())
    ok = r.get("success") is True and r.get("correlation_id") == cid and same
    return ok, f"success={r.get('success')} fields match={same} cid kept=" \
               f"{r.get('correlation_id') == cid}"


def p1_errors():
    cases = [("GET_TRIAL", {"trial_id": str(uuid.uuid4())}),
             ("DELETE_TRIAL", {}),
             ("CREATE_TRIAL", {**TRIAL, "email": "bad", "content": "short"})]
    results = []
    for op, data in cases:
        cid = str(uuid.uuid4())
        r = state["client"].request(op, data, correlation_id=cid)
        results.append(r.get("success") is False and bool(r.get("error"))
                       and r.get("correlation_id") == cid)
    return all(results), f"not found / unknown op / invalid data -> clean error + cid kept: " \
                         f"{results}"


def p1_api():
    base = f"http://127.0.0.1:{PORT_BASE}"
    cid = str(uuid.uuid4())
    r = requests.post(f"{base}/trials", json=TRIAL, headers={"X-Correlation-ID": cid},
                      timeout=20).json()
    cid2 = str(uuid.uuid4())
    g = requests.get(f"{base}/trials/{r.get('trial_id')}", headers={"X-Correlation-ID": cid2},
                     timeout=20).json()
    ok = r.get("correlation_id") == cid and g.get("correlation_id") == cid2 and g.get("success")
    return ok, f"POST/GET via {base}: success={g.get('success')} header cid kept={ok}"


# ---------------- Part 2 ----------------
def p2_topics():
    info = topic_info()
    want = {INBOX: 1, TASKS: 2, DRAFTS: 1, FINAL: 1}
    ok = all(info.get(t) == n for t, n in want.items())
    return ok, ", ".join(f"{t}={info.get(t)}" for t in want)


def p2_start_agents():
    state["agents"] = [Agent("planner.py"), Agent("writer.py"), Agent("reviewer.py")]
    ready = [a.wait("Consumer is ready", 90) for a in state["agents"]]
    both = state["agents"][1].wait("ASSIGNED partitions=[0, 1]", 30)
    return all(ready) and both, f"planner/writer/reviewer ready={ready} " \
                                f"writer owns both task partitions={both}"


def p2_pipeline():
    start = end_offsets(FINAL)
    cid = str(uuid.uuid4())
    producer().send(INBOX, key=cid, value={"correlation_id": cid, "sent_at": "verify",
                    "question": "What does Recruiting status mean for a clinical trial?"}
                    ).get(timeout=10)
    hits = wait_for(FINAL, start, cid, timeout=180)
    final = hits[0] if hits else {}
    ok = final.get("status") in ("approved", "rejected") and bool(final.get("answer")) \
        and final.get("correlation_id") == cid
    return ok, f"inbox -> final: status={final.get('status')} answer words=" \
               f"{len(str(final.get('answer', '')).split())} cid kept={ok}"


# ---------------- Part 3 ----------------
def p3_dead_letter_topic():
    info = topic_info()
    return DEAD_LETTER in info, f"{DEAD_LETTER} partitions={info.get(DEAD_LETTER)}"


def p3_idempotency():
    start = end_offsets(DRAFTS)
    cid = str(uuid.uuid4())
    msg = {"correlation_id": cid, "question": "Verify duplicate", "plan": PLAN,
           "planned_at": "verify"}
    meta = None
    for _ in range(2):
        meta = producer().send(TASKS, key=cid, value=msg).get(timeout=10)
    wait_for(DRAFTS, start, cid, timeout=120)
    time.sleep(4)
    drafts = [m for m in read_since(DRAFTS, start) if m.get("correlation_id") == cid]
    state["commit_check"] = (meta.partition, meta.offset)
    return len(drafts) == 1, f"same message delivered twice -> drafts={len(drafts)} (want 1)"


def p3_commit_after_success():
    part, off = state["commit_check"]
    c = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=f"{PREFIX}_writer",
                      enable_auto_commit=False)
    committed = c.committed(TopicPartition(TASKS, part))
    c.close()
    return committed == off + 1, f"writer committed p{part}={committed} after last message " \
                                 f"at offset {off}"


def p3_poison():
    d_start, dl_start = end_offsets(DRAFTS), end_offsets(DEAD_LETTER)
    bad, good = str(uuid.uuid4()), str(uuid.uuid4())
    producer().send(TASKS, key=bad, partition=0, value={"correlation_id": bad,
                    "question": "poison", "plan": None}).get(timeout=10)
    producer().send(TASKS, key=good, partition=0, value={"correlation_id": good,
                    "question": "What is a Phase II trial?", "plan": PLAN,
                    "planned_at": "verify"}).get(timeout=10)
    dead = wait_for(DEAD_LETTER, dl_start, bad, timeout=60)
    drafted = wait_for(DRAFTS, d_start, good, timeout=120)
    ok = bool(dead) and dead[0].get("attempts") == 3 and bool(drafted)
    return ok, f"poison in {DEAD_LETTER}={len(dead)} attempts=" \
               f"{dead[0].get('attempts') if dead else None}; next message drafted={bool(drafted)}"


def p3_partition_key():
    parts: dict[str, set] = {}
    for n in range(9):
        entity = ["NCT05512874", "NCT04811023", "NCT06120458"][n % 3]
        meta = producer().send(TASKS, key=entity, value={
            "correlation_id": str(uuid.uuid4()), "question": "key check", "plan": PLAN,
            "entity": entity, "seq": n // 3 + 1, "planned_at": "verify"}).get(timeout=10)
        parts.setdefault(entity, set()).add(meta.partition)
    ok = all(len(p) == 1 for p in parts.values())
    return ok, f"key=trial id -> partitions per trial: " \
               f"{ {e: sorted(p) for e, p in parts.items()} }"


def main():
    print(f"HW8 verification   Run by: Ani Taraiya ({PREFIX})   "
          f"{datetime.now():%Y-%m-%d %H:%M:%S}   commit {git('rev-parse', '--short', 'HEAD')}")
    checks = [
        check("Part 1", "docker containers running", p1_containers),
        check("Part 1", "request/response topics exist", p1_topics),
        check("Part 1", "CREATE_TRIAL over Kafka", p1_create),
        check("Part 1", "GET_TRIAL round trip", p1_get),
        check("Part 1", "clean errors keep correlation_id", p1_errors),
        check("Part 1", "FastAPI wrapper on PORT_BASE", p1_api),
        check("Part 2", "four topics, tasks has 2 partitions", p2_topics),
        check("Part 2", "planner, writer, reviewer start", p2_start_agents),
        check("Part 2", "question reaches s3209_final", p2_pipeline),
        check("Part 3", "dead-letter topic exists", p3_dead_letter_topic),
        check("Part 3", "duplicate replay has no extra draft", p3_idempotency),
        check("Part 3", "offset committed after success", p3_commit_after_success),
        check("Part 3", "poison -> dead letter, next message runs", p3_poison),
        check("Part 3", "same key -> same partition", p3_partition_key),
    ]
    for agent in state.get("agents", []):
        agent.stop()
    if "client" in state:
        state["client"].close()
    passed = sum(c["pass"] for c in checks)
    result = {
        "homework": "HW8", "sid4": SID4, "prefix": PREFIX, "port_base": PORT_BASE,
        "commit": git("rev-parse", "HEAD"),
        "code_clean": git("status", "--porcelain", "code", "Makefile") == "",
        "model": MODEL, "model_settings": {"temperature": 0.0, "seed": SEED},
        "kafka": {"bootstrap": BOOTSTRAP, "image": "apache/kafka:3.8.0"},
        "seed": SEED, "verify_seed": VERIFY_SEED,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {"passed": passed, "total": len(checks)},
        "checks": checks,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print(f"\n{passed}/{len(checks)} checks passed -> {OUT.relative_to(ROOT)}")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
