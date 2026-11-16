"""HW10 Part 2-3: DeepEval GEval judge on a local Ollama model, scored 1-5.

The judge goes through src/model_client.py (temperature 0, fixed seed, JSON mode).
Each metric call is bounded: HTTP timeout in the client + a hard wall-clock timeout.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("DEEPEVAL_GRPC_LOGGING", "NO")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import deepeval  # noqa: E402
from deepeval.metrics import GEval  # noqa: E402
from deepeval.metrics.g_eval import Rubric  # noqa: E402
from deepeval.models import DeepEvalBaseLLM  # noqa: E402
from deepeval.test_case import LLMTestCase  # noqa: E402

try:
    from deepeval.test_case import SingleTurnParams as Params
except ImportError:  # deepeval < 4
    from deepeval.test_case import LLMTestCaseParams as Params

from model_client import ModelClient  # noqa: E402

JUDGE_MODEL = os.getenv("JUDGE_MODEL", os.getenv("OLLAMA_MODEL", "llama3.1:8b"))
JUDGE_TEMPERATURE = 0.0
JUDGE_SEED = 3209
HTTP_TIMEOUT_S = 60
METRIC_TIMEOUT_S = 90
JUDGE_MAX_TOKENS = 2048
PARSE_TRIES = 4

RUBRIC = [Rubric(score_range=(1, 1), expected_outcome="Very poor: wrong, off-topic or unusable."),
          Rubric(score_range=(2, 2), expected_outcome="Poor: major gaps or errors."),
          Rubric(score_range=(3, 3), expected_outcome="Adequate: partly useful, some gaps."),
          Rubric(score_range=(4, 4), expected_outcome="Good: accurate and useful, minor gaps."),
          Rubric(score_range=(5, 5), expected_outcome="Excellent: accurate, complete, clear.")]

PLAN_STEPS = [
    "Read the user question and any trial records in the input.",
    "Check whether the plan's steps, followed in order, would lead a writer to a complete answer.",
    "Penalize steps that are vague, off-topic, redundant, or that invent trial facts.",
    "Give 5 for a specific, ordered, sufficient plan and 1 for a useless plan."]
HELP_STEPS = [
    "Read the user question and any trial records in the input.",
    "Check that the answer addresses the question directly and is relevant to clinical trials.",
    "Check accuracy: values for status, slots or sponsor must match the trial records; "
    "invented IDs, dates or counts are serious errors.",
    "Judge usefulness to a trial coordinator: clear, specific and actionable.",
    "Give 5 for an accurate, complete, clear answer and 1 for a wrong or unhelpful one."]


def json_part(text: str) -> str:
    """Return the {...} object inside text (the model sometimes adds words around it)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object in reply: {text[:60]!r}")
    return text[start:end + 1]


class LocalJudge(DeepEvalBaseLLM):
    """DeepEval model wrapper around the repo's Ollama ModelClient."""

    def __init__(self, model: str = JUDGE_MODEL) -> None:
        """Return nothing; build the client with documented, fixed settings."""
        self.name = model
        self.client = ModelClient(model=model, temperature=JUDGE_TEMPERATURE, seed=JUDGE_SEED,
                                  num_predict=JUDGE_MAX_TOKENS,
                                  client_kwargs={"timeout": HTTP_TIMEOUT_S})

    def load_model(self):
        """Return the underlying client."""
        return self.client

    def generate(self, prompt: str, schema=None):
        """Return the judge reply, parsed into schema; one retry on an empty or cut-off reply."""
        error = None
        for _ in range(PARSE_TRIES):
            text = self.client.complete([{"role": "user", "content": prompt}]).text
            if schema is None:
                return text
            try:
                return schema.model_validate(json.loads(json_part(text)))
            except ValueError as exc:
                error = exc
        raise ValueError(f"judge reply was not valid JSON after {PARSE_TRIES} tries: {error}")

    async def a_generate(self, prompt: str, schema=None):
        """Return the same reply as generate (sync under the hood)."""
        return self.generate(prompt, schema)

    def get_model_name(self) -> str:
        """Return the Ollama model tag."""
        return f"ollama:{self.name}"


def settings() -> dict:
    """Return the judge settings saved with every result."""
    return {"framework": f"deepeval {deepeval.__version__} GEval", "model": JUDGE_MODEL,
            "temperature": JUDGE_TEMPERATURE, "seed": JUDGE_SEED, "scale": "1-5 rubric",
            "http_timeout_s": HTTP_TIMEOUT_S, "metric_timeout_s": METRIC_TIMEOUT_S,
            "max_tokens": JUDGE_MAX_TOKENS, "parse_tries": PARSE_TRIES}


def make_metric(kind: str, judge: LocalJudge) -> GEval:
    """Return the GEval metric 'plan' or 'helpfulness' with fixed steps and the 1-5 rubric."""
    if kind not in ("plan", "helpfulness"):
        raise ValueError("kind must be 'plan' or 'helpfulness'")
    name = "Plan Quality" if kind == "plan" else "Helpfulness"
    steps = PLAN_STEPS if kind == "plan" else HELP_STEPS
    return GEval(name=name, evaluation_steps=steps, rubric=RUBRIC, model=judge,
                 evaluation_params=[Params.INPUT, Params.ACTUAL_OUTPUT],
                 async_mode=False, verbose_mode=False)


def to_five(score: float | None) -> int | None:
    """Return a GEval score normalized to 0-1 back on the 1-5 scale."""
    if score is None:
        return None
    if not 0.0 <= score <= 1.0:
        raise ValueError("GEval score must be in [0, 1]")
    return int(round(1 + 4 * score))


def score(kind: str, question: str, output: str, judge: LocalJudge) -> dict:
    """Return {'score' 1-5, 'reason', 'status', 'error'}; never waits past METRIC_TIMEOUT_S."""
    if not output or not str(output).strip():
        return {"score": None, "reason": "", "status": "error", "error": "empty output"}
    metric = make_metric(kind, judge)
    case = LLMTestCase(input=question, actual_output=str(output))
    pool = cf.ThreadPoolExecutor(max_workers=1)
    try:
        pool.submit(metric.measure, case).result(timeout=METRIC_TIMEOUT_S)
        return {"score": to_five(metric.score), "reason": metric.reason,
                "status": "ok", "error": None}
    except cf.TimeoutError:
        return {"score": None, "reason": "", "status": "error",
                "error": f"judge timeout after {METRIC_TIMEOUT_S}s"}
    except Exception as exc:
        return {"score": None, "reason": "", "status": "error",
                "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
