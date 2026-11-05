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

from common import BOOTSTRAP, FINAL, INBOX, now, producer  # noqa: E402


class AgentPipeline:
    """Kafka client for the HW8 agent pipeline (one final-topic reader kept open)."""

    def __init__(self, timeout_s: int = 300) -> None:
        """Return nothing; open the producer and a reader positioned at the end of FINAL."""
        self.timeout_s = timeout_s
        self.out = producer()
        self.final = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None,
                                   enable_auto_commit=False)
        self.tp = TopicPartition(FINAL, 0)
        self.final.assign([self.tp])
        self.final.seek_to_end(self.tp)
        self.final.position(self.tp)

    def ask(self, question: str, facts: str = "") -> dict:
        """Return the Reviewer's final message for this question (raises TimeoutError)."""
        cid = str(uuid.uuid4())
        msg = {"correlation_id": cid, "question": question, "facts": facts, "sent_at": now()}
        self.out.send(INBOX, key=cid, value=msg).get(timeout=10)
        deadline = time.time() + self.timeout_s
        while time.time() < deadline:
            for records in self.final.poll(timeout_ms=200).values():
                for rec in records:
                    result = json.loads(rec.value)
                    if result.get("correlation_id") == cid:
                        return result
        raise TimeoutError(f"no final message for {cid} within {self.timeout_s}s")
