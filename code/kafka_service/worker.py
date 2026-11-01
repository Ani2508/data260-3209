"""HW8 Part 1 worker: consume s3209_trial_requests, reply on the topic named by reply_to.

Run:  python code/kafka_service/worker.py   (or the 'worker' service in docker-compose)
"""
import json

from kafka import KafkaConsumer, KafkaProducer

from config import (
    BOOTSTRAP,
    PREFIX,
    REQUEST_TOPIC,
    RESPONSE_TOPIC,
    RUN_BY,
    WORKER_GROUP,
    get_logger,
)
from trial_service import handle_request

log = get_logger("worker")
TRIALS: dict[str, dict] = {}  # trial_id -> trial (plain dict, per assignment)


def parse(raw: bytes):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None


def process(msg, producer):
    request = parse(msg.value)
    cid = request.get("correlation_id") if isinstance(request, dict) else None
    op = request.get("operation") if isinstance(request, dict) else None
    log.info("RECEIVED  from %s [p%d@%d] cid=%s op=%s", msg.topic, msg.partition,
             msg.offset, cid, op)
    if request is None:
        response = {"correlation_id": None, "success": False, "error": "Invalid JSON"}
    else:
        response = handle_request(TRIALS, request)
    log.info("PROCESSED cid=%s success=%s %s", cid, response["success"],
             response.get("trial_id") or response.get("error") or "")

    reply_to = request.get("reply_to") if isinstance(request, dict) else None
    if not isinstance(reply_to, str) or not reply_to.startswith(f"{PREFIX}_"):
        reply_to = RESPONSE_TOPIC
    producer.send(reply_to, key=cid or "none", value=response).get(timeout=10)
    log.info("REPLIED   to %s cid=%s %s", reply_to, cid, json.dumps(response))


def main():
    # max_poll_records=1 + manual commit: the offset moves only after the reply is written
    consumer = KafkaConsumer(REQUEST_TOPIC, bootstrap_servers=BOOTSTRAP, group_id=WORKER_GROUP,
                             enable_auto_commit=False, auto_offset_reset="earliest",
                             max_poll_records=1)
    producer = KafkaProducer(bootstrap_servers=BOOTSTRAP, acks="all",
                             key_serializer=str.encode,
                             value_serializer=lambda v: json.dumps(v).encode())
    log.info("Run by: %s (%s)   bootstrap=%s", RUN_BY, PREFIX, BOOTSTRAP)
    ready = False
    while True:
        batch = consumer.poll(timeout_ms=1000)
        if not ready and consumer.assignment():
            log.info("Consumer is ready and listening... topic=%s group=%s",
                     REQUEST_TOPIC, WORKER_GROUP)
            ready = True
        for records in batch.values():
            for msg in records:
                process(msg, producer)
                consumer.commit()


if __name__ == "__main__":
    main()
