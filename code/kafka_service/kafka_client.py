"""HW8 Part 1 client: send a request to s3209_trial_requests and wait for the
response with the same correlation_id on s3209_trial_responses.

Used by homework_demo.py and by the FastAPI wrapper (api.py).
"""
import json
import threading
import uuid

from kafka import KafkaConsumer, KafkaProducer, TopicPartition

from config import BOOTSTRAP, REQUEST_TOPIC, RESPONSE_TOPIC, get_logger


class TrialKafkaClient:
    def __init__(self, role: str = "client", bootstrap: str = BOOTSTRAP):
        self.log = get_logger(role)
        self.producer = KafkaProducer(bootstrap_servers=bootstrap, acks="all",
                                      key_serializer=str.encode,
                                      value_serializer=lambda v: json.dumps(v).encode())
        # Read every partition of the response topic from its current end,
        # so this client only sees replies sent after it started.
        self.consumer = KafkaConsumer(bootstrap_servers=bootstrap, group_id=None,
                                      enable_auto_commit=False)
        parts = self.consumer.partitions_for_topic(RESPONSE_TOPIC) or {0}
        tps = [TopicPartition(RESPONSE_TOPIC, p) for p in parts]
        self.consumer.assign(tps)
        self.consumer.seek_to_end(*tps)
        for tp in tps:
            self.consumer.position(tp)
        self._waiting: dict[str, dict] = {}
        self._lock = threading.Lock()
        threading.Thread(target=self._read_responses, daemon=True).start()

    @staticmethod
    def new_correlation_id() -> str:
        return str(uuid.uuid4())

    def _read_responses(self):
        try:
            for msg in self.consumer:
                try:
                    response = json.loads(msg.value)
                except ValueError:
                    continue
                with self._lock:
                    slot = self._waiting.get(response.get("correlation_id"))
                if slot:
                    slot["response"] = response
                    slot["event"].set()
        except Exception:  # consumer closed on shutdown
            return

    def send(self, operation: str, data: dict, correlation_id: str | None = None) -> dict:
        """Publish one request message; returns the message that was sent."""
        cid = correlation_id or self.new_correlation_id()
        message = {"correlation_id": cid, "reply_to": RESPONSE_TOPIC,
                   "operation": operation, "data": data}
        with self._lock:
            self._waiting[cid] = {"event": threading.Event(), "response": None}
        self.producer.send(REQUEST_TOPIC, key=cid, value=message).get(timeout=10)
        self.log.info("SENT      to %s cid=%s %s", REQUEST_TOPIC, cid, json.dumps(message))
        return message

    def wait(self, message: dict, timeout: float = 15.0) -> dict:
        """Block until the response with this message's correlation_id arrives."""
        cid = message["correlation_id"]
        with self._lock:
            slot = self._waiting[cid]
        try:
            if not slot["event"].wait(timeout):
                return {"correlation_id": cid, "operation": message["operation"],
                        "success": False, "error": f"No response within {timeout:.0f}s"}
            response = slot["response"]
            self.log.info("RESPONSE  from %s cid=%s %s", RESPONSE_TOPIC, cid,
                          json.dumps(response))
            return response
        finally:
            with self._lock:
                self._waiting.pop(cid, None)

    def request(self, operation: str, data: dict, correlation_id: str | None = None,
                timeout: float = 15.0) -> dict:
        """Send one request and wait for its response (or time out)."""
        return self.wait(self.send(operation, data, correlation_id), timeout)

    def close(self):
        self.producer.close()
        self.consumer.close()
