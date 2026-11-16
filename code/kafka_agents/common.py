"""HW8 Part 2 shared pieces: topic names, JSON producer, the agent consume loop and the model.

Every agent reads one topic and writes the next one. The offset is committed only
after the outgoing message is acknowledged by Kafka.
"""
import json
import os
import sys
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from kafka import KafkaConsumer, KafkaProducer

warnings.filterwarnings("ignore", message=".*serializer does not implement.*")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "code" / "tracing"))

from model_client import ModelClient  # noqa: E402
from tracer import epoch_ms, queue_span, span  # noqa: E402

SID4 = 3209
PREFIX = f"s{SID4}"
SEED = SID4
RUN_BY = "Ani Taraiya"
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
INBOX, TASKS, DRAFTS, FINAL = (f"{PREFIX}_{t}" for t in ("inbox", "tasks", "drafts", "final"))
TZ = ZoneInfo("America/Los_Angeles")
MAX_TOKENS = 400
MODEL_TIMEOUT_S = 60
DEAD_LETTER = f"{PREFIX}_dead_letter"


def now() -> str:
    return datetime.now(TZ).strftime("%H:%M:%S.%f")[:-3]


def log(agent: str, text: str):
    print(f"{now()} | {PREFIX} {agent:<8} | {text}", flush=True)


def producer() -> KafkaProducer:
    return KafkaProducer(bootstrap_servers=BOOTSTRAP, acks="all", key_serializer=str.encode,
                         value_serializer=lambda v: json.dumps(v).encode())


def model() -> ModelClient:
    # HW10: cap output and wait so a runaway JSON reply fails fast instead of hanging the agent
    return ModelClient(model=MODEL, temperature=0.0, seed=SEED, num_predict=MAX_TOKENS,
                       client_kwargs={"timeout": MODEL_TIMEOUT_S})


def ask_json(llm: ModelClient, system: str, user: str, key: str, tries: int = 2) -> dict:
    """Call the model and return its JSON reply; it must contain `key`."""
    for _ in range(tries):
        text = llm.complete([{"role": "system", "content": system},
                             {"role": "user", "content": user}]).text
        try:
            data = json.loads(text)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get(key) not in (None, "", []):
            return data
    raise ValueError(f"model reply had no '{key}'")


def topic_stage(topic: str) -> str:
    """Return the trace stage for a topic ('s3209_inbox' -> 'inbox')."""
    return topic.split("_", 1)[1]


def run_agent(name: str, in_topic: str, out_topic: str, handle):
    """Consume in_topic one message at a time, send handle(msg) to out_topic, then commit."""
    consumer = KafkaConsumer(in_topic, bootstrap_servers=BOOTSTRAP,
                             group_id=f"{PREFIX}_{name.lower()}", enable_auto_commit=False,
                             auto_offset_reset="earliest", max_poll_records=1)
    out = producer()
    log(name, f"Run by: {RUN_BY} ({PREFIX})   model={MODEL}   {in_topic} -> {out_topic}")
    ready = False
    while True:
        batch = consumer.poll(timeout_ms=1000)
        if not ready and consumer.assignment():
            log(name, f"Consumer is ready and listening... topic={in_topic}")
            ready = True
        for records in batch.values():
            for rec in records:
                msg = json.loads(rec.value)
                cid = msg.get("correlation_id")
                log(name, f"RECEIVED from {in_topic} [p{rec.partition}@{rec.offset}] cid={cid}")
                if cid:  # HW10: queue wait for this topic, then the agent's own span
                    queue_span(cid, topic_stage(in_topic), msg.get("sent_ms"),
                               partition=rec.partition, offset=rec.offset)
                try:
                    with span(cid or "unknown", name.lower(), partition=rec.partition):
                        result = handle(msg)
                except Exception as exc:  # HW10: one bad message must not kill the agent
                    error = f"{type(exc).__name__}: {exc}"
                    bad = {"correlation_id": cid, "error": error, "failed_stage": name.lower(),
                           "source": f"{in_topic} p{rec.partition}@{rec.offset}",
                           "failed_at": now(), "sent_ms": epoch_ms()}
                    out.send(DEAD_LETTER, key=cid or "unknown", value=bad).get(timeout=10)
                    log(name, f"DEAD_LETTER sent to {DEAD_LETTER} cid={cid} {error}")
                    consumer.commit()
                    continue
                result["sent_ms"] = epoch_ms()
                out.send(out_topic, key=cid, value=result).get(timeout=10)
                log(name, f"SENT     to {out_topic} cid={cid} {json.dumps(result)[:160]}")
                consumer.commit()
                log(name, f"COMMIT   {in_topic} p{rec.partition} offset -> {rec.offset + 1}")
