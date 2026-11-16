"""Offline tests for HW10 (no Kafka, Redis, MySQL or Ollama):
python3 code/evaluation/test_hw10.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["S3209_SPAN_FILE"] = os.path.join(tempfile.mkdtemp(), "spans.jsonl")
for sub in ("evaluation", "tracing", "kafka_agents"):
    sys.path.insert(0, str(HERE.parent / sub))

import tracer  # noqa: E402
from evaluator import interpret, match  # noqa: E402
from judge import LocalJudge, score, to_five  # noqa: E402


class FakeJudge(LocalJudge):
    """Judge that always answers with a fixed 1-5 score (no Ollama)."""

    def __init__(self, raw: int) -> None:
        """Return nothing; keep the score to return."""
        self.name, self.raw = "fake", raw

    def generate(self, prompt: str, schema=None):
        """Return a fixed GEval reply."""
        data = {"score": self.raw, "reason": f"fixed {self.raw}"}
        return schema.model_validate(data) if schema else json.dumps(data)


def run_tests() -> int:
    """Return the number of passed tests (AssertionError on the first failure)."""
    # 1-3. spans: written, loaded per trace, error status kept
    tracer.write_span("t1", "cache_lookup", 1000.0, 1012.5, result="miss")
    try:
        with tracer.span("t1", "writer", attempt=1):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    tracer.queue_span("t1", "inbox", tracer.epoch_ms() - 50)
    spans = tracer.load_spans(trace_id="t1")
    assert [s["stage"] for s in spans] == ["cache_lookup", "writer", "inbox"]
    assert spans[0]["duration_ms"] == 12.5 and spans[0]["attrs"]["result"] == "miss"
    assert spans[1]["status"] == "error" and spans[1]["error"] == "RuntimeError: boom"
    assert spans[2]["duration_ms"] >= 50

    # 4. edge cases: unknown stage / missing trace_id rejected, malformed lines skipped
    for bad in (("t1", "nope"), ("", "writer")):
        try:
            tracer.write_span(*bad, 0, 1)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted {bad}")
    with open(tracer.SPAN_FILE, "a") as f:
        f.write("{not json\n")
    assert len(tracer.load_spans(trace_id="t1")) == 3
    assert tracer.queue_span("t1", "inbox", None) is None

    # 5. join on correlation_id: other ids and malformed messages are ignored
    assert match(b'{"correlation_id": "a", "plan": []}', b"a", "a") == {
        "correlation_id": "a", "plan": []}
    assert match(b'{"correlation_id": "b"}', b"b", "a") is None
    assert match(b"{broken", b"a", "a") is None and match(b"[1]", None, "a") is None

    # 6. GEval 0-1 score back to the 1-5 scale
    assert [to_five(x) for x in (0.0, 0.25, 0.5, 0.75, 1.0)] == [1, 2, 3, 4, 5]
    assert to_five(None) is None

    # 7-8. real GEval metric with a fake judge: rubric 1-5 round-trips
    for raw in (1, 3, 5):
        r = score("helpfulness", "q?", "an answer", FakeJudge(raw))
        assert r["status"] == "ok" and r["score"] == raw, r
    assert score("plan", "q?", "  ", FakeJudge(4))["error"] == "empty output"

    # 9. a judge that fails returns an error instead of raising
    class Broken(FakeJudge):
        """Judge whose model is unreachable."""

        def generate(self, prompt, schema=None):
            """Return nothing; always raise like a stopped Ollama."""
            raise ConnectionError("ollama down")

    r = score("helpfulness", "q?", "x", Broken(3))
    assert r["score"] is None and "ollama down" in r["error"]

    # 10a. JSON with extra words around it is still read; no JSON at all is an error
    from judge import json_part

    assert json_part('ok {"score": 4, "reason": "x"} done') == '{"score": 4, "reason": "x"}'
    try:
        json_part("")
    except ValueError:
        pass
    else:
        raise AssertionError("empty reply accepted")

    # 10. final-vs-draft interpretation does not force a positive result
    assert interpret(4, 4, True, "approved").startswith("no improvement")
    assert interpret(3, 4, True, "approved").startswith("no change")
    assert interpret(3, 4, False, "approved") == "improved by 1 point(s)"
    assert interpret(None, 4, False, "x") == "not scored (judge error)"
    return 10


if __name__ == "__main__":
    print(f"HW10 offline tests: {run_tests()} / 10 passed")
