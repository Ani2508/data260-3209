"""HW8 Part 3: Writer consume loop with the four fixes.

- idempotency: a done-marker per correlation_id, so a replayed message has no new side effect
- offset commit: only after the outgoing message is acknowledged (at-least-once)
- bounded retries + s3209_dead_letter: a poison message cannot block the partition
- partition key: set by the sender (key = entity); the loop just logs the partition

Each fix can be switched off with a flag to show the behaviour before the fix.
"""
import json
import time
from pathlib import Path

from kafka import ConsumerRebalanceListener, KafkaConsumer

from common import BOOTSTRAP, MODEL, PREFIX, RUN_BY, log, now, producer

DEAD_LETTER = f"{PREFIX}_dead_letter"
STATE = Path(__file__).resolve().parent / "state"


class LogAssignments(ConsumerRebalanceListener):
    def __init__(self, name: str):
        self.name = name

    def on_partitions_revoked(self, revoked):
        pass

    def on_partitions_assigned(self, assigned):
        log(self.name, f"ASSIGNED partitions={sorted(tp.partition for tp in assigned)}")


def run_reliable(name, in_topic, out_topic, handle, *, idempotent=True, commit_first=False,
                 max_retries=3, dead_letter=True):
    group = f"{PREFIX}_{name.split('-')[0].lower()}"
    consumer = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=group,
                             enable_auto_commit=False, auto_offset_reset="earliest",
                             max_poll_records=1)
    consumer.subscribe([in_topic], listener=LogAssignments(name))
    out = producer()
    done_dir = STATE / group
    done_dir.mkdir(parents=True, exist_ok=True)
    log(name, f"Run by: {RUN_BY} ({PREFIX})   model={MODEL}   {in_topic} -> {out_topic}")
    log(name, f"MODE     idempotency={'on' if idempotent else 'OFF'}   "
              f"commit={'BEFORE work' if commit_first else 'after success'}   "
              f"dead_letter={f'on ({max_retries} tries)' if dead_letter else 'OFF'}")
    ready = False
    while True:
        batch = consumer.poll(timeout_ms=1000)
        if not ready and consumer.assignment():
            log(name, f"Consumer is ready and listening... topic={in_topic} group={group}")
            ready = True
        for records in batch.values():
            for rec in records:
                process(name, rec, consumer, out, handle, done_dir, out_topic,
                        idempotent, commit_first, max_retries, dead_letter)


def commit(name, consumer, rec, note=""):
    consumer.commit()
    log(name, f"COMMIT   {rec.topic} p{rec.partition} offset -> {rec.offset + 1}{note}")


def process(name, rec, consumer, out, handle, done_dir, out_topic,
            idempotent, commit_first, max_retries, dead_letter):
    if commit_first:  # before fix: offset moves before the work is done
        commit(name, consumer, rec, " (before work)")
    try:
        msg = json.loads(rec.value)
    except ValueError:
        msg = None
    cid = msg.get("correlation_id") if isinstance(msg, dict) else None
    log(name, f"RECEIVED from {rec.topic} [p{rec.partition}@{rec.offset}] cid={cid}")

    marker = done_dir / f"{cid}.done"
    if idempotent and cid and marker.exists():  # idempotency: already handled
        log(name, f"DUPLICATE cid={cid} already processed -> skipped, nothing sent")
        commit(name, consumer, rec)
        return

    for attempt in range(1, max_retries + 1):
        try:
            if not isinstance(msg, dict):
                raise ValueError("message is not a JSON object")
            result = handle(msg)
            break
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if not dead_letter:  # before fix: the error kills the consumer
                log(name, f"CRASH    cid={cid} {error} (offset not committed)")
                raise
            log(name, f"RETRY    {attempt}/{max_retries} cid={cid} {error}")
            time.sleep(0.5)
    else:
        bad = {"correlation_id": cid, "error": error, "attempts": max_retries,
               "source": f"{rec.topic} p{rec.partition}@{rec.offset}",
               "raw": rec.value.decode(errors="replace"), "failed_at": now()}
        out.send(DEAD_LETTER, key=cid or "unknown", value=bad).get(timeout=10)
        log(name, f"DEAD_LETTER sent to {DEAD_LETTER} cid={cid} after {max_retries} tries")
        if not commit_first:
            commit(name, consumer, rec)
        return

    result.update(processed_by=name, source_partition=rec.partition)
    out.send(out_topic, key=cid, value=result).get(timeout=10)
    log(name, f"SENT     to {out_topic} cid={cid}")
    if idempotent and cid:
        marker.touch()
    if not commit_first:
        commit(name, consumer, rec)
