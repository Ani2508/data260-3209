"""HW8 shared Kafka settings (PREFIX s3209, PORT_BASE 8509)."""
import logging
import os
import sys
import warnings
from datetime import datetime
from zoneinfo import ZoneInfo

# kafka-python 2.3 warns that plain lambdas are not Serializer classes; they still work.
warnings.filterwarnings("ignore", message=".*serializer does not implement.*")

SID4 = 3209
PREFIX = f"s{SID4}"
PORT_BASE = 8000 + SID4 % 900  # 8509
RUN_BY = "Ani Taraiya"

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
REQUEST_TOPIC = f"{PREFIX}_trial_requests"
RESPONSE_TOPIC = f"{PREFIX}_trial_responses"
WORKER_GROUP = f"{PREFIX}_trial_worker"
LOCAL_TZ = ZoneInfo(os.getenv("LOG_TZ", "America/Los_Angeles"))  # host + container logs


def get_logger(role: str) -> logging.Logger:
    """Logger that prints '<time> | s3209 <role> | message' to stdout."""
    log = logging.getLogger(role)
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter(
            f"%(asctime)s.%(msecs)03d | {PREFIX} {role:<6} | %(message)s", "%H:%M:%S")
        fmt.converter = lambda t: datetime.fromtimestamp(t, LOCAL_TZ).timetuple()
        handler.setFormatter(fmt)
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log
