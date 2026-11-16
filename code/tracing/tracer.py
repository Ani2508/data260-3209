"""HW10 Part 4: structured JSON spans keyed by trace_id (= the HW8 correlation_id).

Every stage appends one JSON line to reports/hw10/raw/spans.jsonl:
  trace_id, stage, start, end, start_ms, end_ms, duration_ms, status, error, attrs
Topic stages (inbox, tasks, drafts, final) are queue waits: sent_ms -> received.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SPAN_FILE = Path(os.getenv("S3209_SPAN_FILE", ROOT / "reports/hw10/raw/spans.jsonl"))
TZ = ZoneInfo("America/Los_Angeles")
QUEUE_STAGES = ("inbox", "tasks", "drafts", "final")
WORK_STAGES = ("cache_lookup", "facts", "planner", "writer", "reviewer", "evaluator")
STAGES = ("request", *WORK_STAGES, *QUEUE_STAGES, "dead_letter")
STAGE_ORDER = ("request", "cache_lookup", "facts", "inbox", "planner", "tasks", "writer",
               "drafts", "reviewer", "final", "dead_letter", "evaluator")


def epoch_ms() -> float:
    """Return the current wall-clock time in epoch milliseconds."""
    return round(time.time() * 1000, 1)


def iso(ms: float) -> str:
    """Return an epoch-ms value as local ISO time with milliseconds."""
    return datetime.fromtimestamp(ms / 1000, TZ).isoformat(timespec="milliseconds")


def write_span(trace_id: str, stage: str, start_ms: float, end_ms: float,
               status: str = "ok", error: str | None = None, path: Path | None = None,
               **attrs) -> dict:
    """Return the span after appending it as one JSON line (file-locked across processes)."""
    if not trace_id:
        raise ValueError("trace_id is required")
    if stage not in STAGES:
        raise ValueError(f"unknown stage '{stage}'")
    if status not in ("ok", "error"):
        raise ValueError("status must be 'ok' or 'error'")
    span = {"trace_id": trace_id, "stage": stage, "start": iso(start_ms), "end": iso(end_ms),
            "start_ms": start_ms, "end_ms": end_ms,
            "duration_ms": round(max(end_ms - start_ms, 0.0), 1),
            "status": status, "error": error, "attrs": attrs}
    target = path or SPAN_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(span, default=str) + "\n")
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)
    return span


@contextmanager
def span(trace_id: str, stage: str, **attrs):
    """Yield a dict for extra attrs; write an ok span, or an error span and re-raise."""
    start = epoch_ms()
    extra = dict(attrs)
    try:
        yield extra
    except Exception as exc:
        write_span(trace_id, stage, start, epoch_ms(), "error",
                   f"{type(exc).__name__}: {exc}", **extra)
        raise
    write_span(trace_id, stage, start, epoch_ms(), **extra)


def queue_span(trace_id: str, stage: str, sent_ms: float | None, **attrs) -> dict | None:
    """Return the queue-wait span from sent_ms to now (None if the sender gave no sent_ms)."""
    if sent_ms is None or stage not in QUEUE_STAGES:
        return None
    return write_span(trace_id, stage, float(sent_ms), epoch_ms(), **attrs)


def load_spans(path: Path | None = None, trace_id: str | None = None) -> list[dict]:
    """Return the spans in the file (optionally one trace), skipping malformed lines."""
    target = path or SPAN_FILE
    if not target.exists():
        return []
    out = []
    for line in target.read_text(encoding="utf-8").splitlines():
        try:
            s = json.loads(line)
        except ValueError:
            continue
        if isinstance(s, dict) and (trace_id is None or s.get("trace_id") == trace_id):
            out.append(s)
    return out


def journey(spans: list[dict]) -> list[dict]:
    """Return one trace's spans in stage order, then by start time."""
    rank = {s: i for i, s in enumerate(STAGE_ORDER)}
    return sorted(spans, key=lambda s: (s["start_ms"], rank.get(s["stage"], 99)))
