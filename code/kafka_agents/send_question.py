"""HW8 Part 2: send one question to s3209_inbox and read the result from s3209_final.

Run:  python code/kafka_agents/send_question.py ["your question"]
"""
import json
import sys
import time
import uuid

from kafka import KafkaConsumer, TopicPartition

from common import BOOTSTRAP, FINAL, INBOX, PREFIX, ROOT, RUN_BY, log, now, producer

QUESTION = ("What should a patient check before joining a recruiting Phase II "
            "clinical trial for type 2 diabetes?")
RUN_LOG = ROOT / "reports/hw08/RUN_LOG.txt"
RAW = ROOT / "reports/hw08/raw"


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else QUESTION
    log("YOU", f"Run by: {RUN_BY} ({PREFIX})")
    final = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None, enable_auto_commit=False)
    tp = TopicPartition(FINAL, 0)
    final.assign([tp])
    final.seek_to_end(tp)
    final.position(tp)

    cid = str(uuid.uuid4())
    msg = {"correlation_id": cid, "question": question, "sent_at": now()}
    producer().send(INBOX, key=cid, value=msg).get(timeout=10)
    log("YOU", f"SENT     to {INBOX} cid={cid} {json.dumps(msg)}")

    deadline = time.time() + 300
    while time.time() < deadline:
        for records in final.poll(timeout_ms=1000).values():
            for rec in records:
                result = json.loads(rec.value)
                if result.get("correlation_id") != cid:
                    continue
                log("YOU", f"FINAL    from {FINAL} cid={cid} status={result['status']}")
                print(json.dumps(result, indent=2))
                print(f"correlation_id preserved: {result['correlation_id'] == cid}")
                RAW.mkdir(parents=True, exist_ok=True)
                (RAW / "part2_final.json").write_text(json.dumps(result, indent=2) + "\n")
                show_journey(cid)
                return
    sys.exit(f"no final message for {cid} within 300s")


STAGES = [("YOU", "SENT"), ("PLANNER", "RECEIVED"), ("PLANNER", "SENT"),
          ("WRITER", "RECEIVED"), ("WRITER", "SENT"), ("REVIEWER", "RECEIVED"),
          ("REVIEWER", "SENT"), ("YOU", "FINAL")]


def show_journey(cid: str):
    """One line per stage for this correlation_id, read from RUN_LOG (agents log there via make)."""
    if not RUN_LOG.exists():
        return
    time.sleep(0.5)
    found = {}
    for line in RUN_LOG.read_text().splitlines():
        text = line.split("] ", 1)[-1]
        if cid not in line or text.startswith(" "):  # skip earlier journey printouts
            continue
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 3:
            continue
        agent, action = parts[1].split()[-1], parts[2].split()[0]
        if (agent, action) in STAGES and (agent, action) not in found:
            found[(agent, action)] = text.split(" {")[0]
    print(f"\nmessage journey for cid={cid}")
    for stage in STAGES:
        if stage in found:
            print("  " + found[stage])


if __name__ == "__main__":
    main()
