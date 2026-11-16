"""HW10 Part 2: evaluator for the Planner -> Writer -> Reviewer pipeline.

collect(): reads s3209_tasks (plan), s3209_drafts (draft) and s3209_final (final) and joins
them on correlation_id. evaluate_trace(): scores the four criteria with the GEval judge and
writes one 'evaluator' span under the same trace_id. Both are bounded by deadlines.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for sub in ("code/kafka_agents", "code/tracing", "code/evaluation"):
    sys.path.insert(0, str(ROOT / sub))

from tracer import epoch_ms, span  # noqa: E402

RAW = ROOT / "reports/hw10/raw"
RESULTS = RAW / "eval_results.jsonl"
COLLECT_TIMEOUT_S = 20
NEEDED = {"plan": "tasks", "draft": "drafts", "final": "final"}


def match(raw: bytes, key: bytes | None, cid: str) -> dict | None:
    """Return the decoded message if it belongs to cid; None if not ours or malformed."""
    if key is not None and key.decode(errors="replace") != cid:
        return None
    try:
        msg = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return msg if isinstance(msg, dict) and msg.get("correlation_id") == cid else None


def collect(cid: str, since_ms: float, timeout_s: int = COLLECT_TIMEOUT_S) -> dict:
    """Return {'plan','draft','final'} messages + Kafka sources for cid, plus 'missing'."""
    from kafka import KafkaConsumer, TopicPartition

    from common import BOOTSTRAP, DRAFTS, FINAL, TASKS

    if not cid:
        raise ValueError("cid is required")
    topics = {"plan": TASKS, "draft": DRAFTS, "final": FINAL}
    consumer = KafkaConsumer(bootstrap_servers=BOOTSTRAP, group_id=None,
                             enable_auto_commit=False, request_timeout_ms=10000)
    found, sources, skipped = {}, {}, 0
    try:
        tps = [TopicPartition(t, p) for t in topics.values()
               for p in sorted(consumer.partitions_for_topic(t) or [])]
        consumer.assign(tps)
        offsets = consumer.offsets_for_times({tp: int(since_ms) - 1000 for tp in tps})
        for tp in tps:
            if offsets.get(tp) is None:
                consumer.seek_to_end(tp)
            else:
                consumer.seek(tp, offsets[tp].offset)
        by_topic = {v: k for k, v in topics.items()}
        deadline = time.time() + timeout_s
        while len(found) < 3 and time.time() < deadline:
            for tp, records in consumer.poll(timeout_ms=500).items():
                for rec in records:
                    msg = match(rec.value, rec.key, cid)
                    if msg is None:
                        skipped += 1
                        continue
                    kind = by_topic[tp.topic]
                    found.setdefault(kind, msg)
                    sources.setdefault(kind, {"topic": tp.topic, "partition": tp.partition,
                                              "offset": rec.offset, "timestamp_ms": rec.timestamp})
    finally:
        consumer.close()
    return {**found, "sources": sources, "skipped": skipped,
            "missing": [k for k in topics if k not in found]}


def interpret(draft: int | None, final: int | None, same_text: bool, status: str) -> str:
    """Return a one-line reading of the final-vs-draft comparison."""
    if draft is None or final is None:
        return "not scored (judge error)"
    diff = final - draft
    if same_text:
        return (f"no change: Reviewer {status} the draft and passed the same text on; "
                f"diff {diff:+d} is judge noise only" if diff else
                f"no improvement: Reviewer {status} the draft without rewriting it")
    if diff > 0:
        return f"improved by {diff} point(s)"
    return "no improvement" if diff == 0 else f"final scored {abs(diff)} point(s) lower"


def evaluate_trace(cid: str, since_ms: float, judge=None, save: bool = True) -> dict:
    """Return the evaluation record for one trace (plan, draft, final, four criteria)."""
    record = {"trace_id": cid, "evaluated_at_ms": epoch_ms(), "status": "ok", "error": None}
    try:
        _run(cid, since_ms, judge, record)
    except Exception as exc:  # bounded failure: the record keeps the error, nothing hangs
        record.update(status="error", error=record["error"] or f"{type(exc).__name__}: {exc}")
    if save:
        RAW.mkdir(parents=True, exist_ok=True)
        with open(RESULTS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    return record


def _run(cid: str, since_ms: float, judge, record: dict) -> None:
    """Return nothing; fill record in place inside one 'evaluator' span (raises on error)."""
    from judge import LocalJudge, score, settings

    with span(cid, "evaluator") as attrs:
        msgs = collect(cid, since_ms)
        record.update(sources=msgs["sources"], skipped_messages=msgs["skipped"])
        if msgs["missing"]:
            record.update(status="error", error=f"missing messages: {msgs['missing']}")
            attrs.update(status_detail=record["error"])
            raise RuntimeError(record["error"])
        plan_msg, draft_msg, final_msg = msgs["plan"], msgs["draft"], msgs["final"]
        question = plan_msg["question"]
        facts = plan_msg.get("facts", "")
        judge_input = question + (f"\nTrial records:\n{facts}" if facts else "")
        plan_text = "\n".join(f"{i}. {s}" for i, s in enumerate(plan_msg["plan"], 1))
        draft, final = draft_msg["draft"], final_msg["answer"]
        judge = judge or LocalJudge()
        record.update(question=question, facts=facts, plan=plan_msg["plan"], draft=draft,
                      final_answer=final, review_status=final_msg.get("status"),
                      review_notes=final_msg.get("review_notes"), judge=settings())
        p = score("plan", judge_input, plan_text, judge)
        w = score("helpfulness", judge_input, draft, judge)
        f = score("helpfulness", judge_input, final, judge)
        same = draft.strip() == final.strip()
        diff = None if w["score"] is None or f["score"] is None else f["score"] - w["score"]
        record["scores"] = {
            "plan_quality": {"score": p["score"], "reason": p["reason"], "error": p["error"]},
            "writer_helpfulness": {"score": w["score"], "reason": w["reason"],
                                   "trace_id": cid, "error": w["error"]},
            "final_helpfulness": {"score": f["score"], "reason": f["reason"],
                                  "final_answer": final, "error": f["error"]},
            "improvement": {"draft_score": w["score"], "final_score": f["score"], "diff": diff,
                            "same_text": same,
                            "interpretation": interpret(w["score"], f["score"], same,
                                                        final_msg.get("status", "?"))}}
        errors = [x["error"] for x in (p, w, f) if x["error"]]
        attrs.update(judge=settings()["model"], plan=p["score"], draft=w["score"],
                     final=f["score"], judge_errors=len(errors))
        if errors:
            record.update(status="error", error="; ".join(errors))
            raise RuntimeError(record["error"])
