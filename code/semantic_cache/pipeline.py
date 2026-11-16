"""HW9 Part 2: send one question through the HW8 Planner -> Writer -> Reviewer pipeline.

The question goes to s3209_inbox; the reply is read from s3209_final by correlation_id.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

from kafka import KafkaConsumer, TopicPartition

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "kafka_agents"))

from common import BOOTSTRAP, FINAL, INBOX, PREFIX, epoch_ms, now, producer  # noqa: E402
from tracer import queue_span  # noqa: E402

DEAD_LETTER = f"{PREFIX}_dead_letter"


class AgentPipeline:
    """Kafka client for the HW8 agent pipeline (one final-topic reader kept open)."""

    def __init__(self, timeout_s: int = 300) -> None:
        """Return nothing; open the producer and a reader positioned at the end of FINAL."""
        self.timeout_s = timeout_s
        self.out = producer()
        self.final = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None,
                                   enable_auto_commit=False)
        self.tp = TopicPartition(FINAL, 0)
        tps = [self.tp]
        if self.final.partitions_for_topic(DEAD_LETTER):  # HW10: fail fast on dead letters
            tps.append(TopicPartition(DEAD_LETTER, 0))
        self.final.assign(tps)
        for tp in tps:
            self.final.seek_to_end(tp)
            self.final.position(tp)

    def ask(self, question: str, facts: str = "", trace_id: str | None = None,
            fail_stage: str | None = None) -> dict:
        """Return the Reviewer's final message (TimeoutError; RuntimeError on dead letter)."""
        cid = trace_id or str(uuid.uuid4())  # HW10: trace_id IS the correlation_id
        msg = {"correlation_id": cid, "question": question, "facts": facts, "sent_at": now(),
               "sent_ms": epoch_ms()}
        if fail_stage:
            msg["fail_stage"] = fail_stage
        self.out.send(INBOX, key=cid, value=msg).get(timeout=10)
        deadline = time.time() + self.timeout_s
        while time.time() < deadline:
            for tp, records in self.final.poll(timeout_ms=200).items():
                for rec in records:
                    result = json.loads(rec.value)
                    if result.get("correlation_id") != cid:
                        continue
                    if tp.topic == DEAD_LETTER:
                        raise RuntimeError(f"dead letter from {result.get('failed_stage')}: "
                                           f"{result.get('error')}")
                    queue_span(cid, "final", result.get("sent_ms"), offset=rec.offset)
                    return result
        raise TimeoutError(f"no final message for {cid} within {self.timeout_s}s")
