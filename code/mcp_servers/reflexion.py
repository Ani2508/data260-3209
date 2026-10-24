"""HW7 Part 3 - bounded Reflexion on top of the Part 2 agent loop.

For each fixed task: run the agent -> deterministic verifier -> on failure, write ONE short
reflection (failure + revised strategy, with evidence) -> retry with that reflection in context.
Bounds: at most MAX_RETRIES retries, a hard tool-call budget and a hard token budget.
Stop reasons: success | budget_exhausted | human_review.

Reflections are untrusted data: they are stored per (user, run), sanitised, length-capped and
only ever shown to the model as a labelled user-role note. They can never change the system
prompt, the tool list or the safety rule in execute_tool.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from agent_loop import AdapterModel, AgentResult, run_agent
from tool_gateway import default_store

ROOT = Path(__file__).resolve().parents[2]
REFLECTIONS_PATH = ROOT / "reports" / "hw07" / "raw" / "part3_reflections.jsonl"
MAX_RETRIES = 2
TOOL_BUDGET = 12          # tool calls across all attempts of one task
TOKEN_BUDGET = 30000      # input + output tokens across attempts and reflections
NCT_RE = re.compile(r"NCT\d{8}")
TRIAL_ID_RE = re.compile(r"\btrial\s*(?:id\s*)?#?\s*(\d+)\b", re.IGNORECASE)


# ---------------------------------------------------------------- ground truth (from MySQL)
def ground_truth(store=None) -> dict:
    """Return the facts each task's answer must contain, read directly from the database."""
    store = store or default_store()
    diabetes = store.search("Diabetes", None, 25)
    first = store.get(diabetes[0]["id"])
    stats = {g["grp"]: g["trials"] for g in store.stats("status")}
    migraine = store.search("Migraine", "Recruiting", 25)
    hyper = store.search("Hypertension", None, 25)[:2]
    return {"A": {"trial": first},
            "B": {"recruiting": stats.get("Recruiting", 0),
                  "examples": [store.get(r["id"]) for r in migraine]},
            "C": {"trials": [store.get(r["id"]) for r in hyper]}}


# ---------------------------------------------------------------- deterministic checks
def _mentions(answer: str, trial: dict, strict: bool) -> bool:
    """Return True if the answer identifies the trial (strict: NCT id only)."""
    if trial["nct_id"] in answer:
        return True
    if strict:
        return False
    ids = {int(x) for x in TRIAL_ID_RE.findall(answer)}
    return trial["id"] in ids or trial["trial_title"].lower() in answer.lower()


def _status_ok(answer: str, status: str, strict: bool) -> bool:
    """Return True if the answer states the status (lenient: also reworded forms)."""
    if status.lower() in answer.lower():
        return True
    if strict:
        return False
    words = r"\W+(?:but\s+|and\s+)?".join(re.findall(r"[a-z]+", status.lower()))
    return re.search(words, answer.lower()) is not None


def _has_number(answer: str, n: int) -> bool:
    """Return True if the integer n appears as a whole number in the answer."""
    return re.search(rf"(?<![\d.]){n}(?![\d.])", answer) is not None


def verify(task: str, result: AgentResult, truth: dict, strict: bool = True) -> dict:
    """Return {passed, assertions:[{check, ok}]} for one task (deterministic, no model)."""
    ans, calls = result.answer, [c for c in result.tool_calls if c["ok"]]
    checks = []
    if task == "A":
        t = truth["A"]["trial"]
        checks.append(("get_trial called for the first search result",
                       any(c["name"] == "get_trial" and c["arguments"].get("trial_id") == t["id"]
                           for c in calls)))
        checks.append((f"answer identifies trial {t['id']} ({t['nct_id']})",
                       _mentions(ans, t, strict)))
        checks.append((f"answer states status '{t['status']}'",
                       _status_ok(ans, t["status"], strict)))
    elif task == "B":
        n, ex = truth["B"]["recruiting"], truth["B"]["examples"]
        checks.append(("trial_stats called", any(c["name"] == "trial_stats" for c in calls)))
        checks.append((f"answer gives the Recruiting count {n}", _has_number(ans, n)))
        checks.append(("answer names a recruiting Migraine trial "
                       f"({', '.join(e['nct_id'] for e in ex)})",
                       any(_mentions(ans, e, strict) for e in ex)))
    elif task == "C":
        for t in truth["C"]["trials"]:
            checks.append((f"answer identifies trial {t['id']} ({t['nct_id']})",
                           _mentions(ans, t, strict)))
            checks.append((f"answer states '{t['status']}' for trial {t['id']}",
                           _status_ok(ans, t["status"], strict)))
            checks.append((f"answer gives {t['enrollment_slots']} slots for trial {t['id']}",
                           _has_number(ans, t["enrollment_slots"])))
    else:
        raise ValueError(f"unknown task {task!r}")
    if result.stop_reason != "final_answer":
        checks.append(("run ended with a final answer", False))
    return {"passed": all(ok for _, ok in checks),
            "assertions": [{"check": c, "ok": ok} for c, ok in checks]}


def unsupported_claims(result: AgentResult) -> list[str]:
    """Return identifiers in the answer (NCT ids, trial ids) that no tool result contains."""
    seen = json.dumps([c["result"] for c in result.tool_calls], default=str)
    seen_ids = {int(x) for x in re.findall(r'"id": (\d+)', seen)}
    out = [n for n in NCT_RE.findall(result.answer) if n not in seen]
    out += [f"trial {i}" for i in map(int, TRIAL_ID_RE.findall(result.answer))
            if i not in seen_ids]
    return out


# ---------------------------------------------------------------- reflections (untrusted)
INJECTION_RE = re.compile(r"ignore (all|previous|the)|system prompt|you are now|new rule|"
                          r"disable|bypass|permission|delete|drop table|execute_tool",
                          re.IGNORECASE)


def sanitize(text: str, limit: int = 240) -> tuple[str, bool]:
    """Return (cleaned text, flagged) - one line, length-capped, injection-like text removed."""
    text = " ".join(str(text).split())[:limit]
    if INJECTION_RE.search(text):
        return "(removed: reflection tried to change rules or permissions)", True
    return text, False


class ReflectionStore:
    """Append-only JSONL store; reads are isolated to one (user_id, run_id)."""

    def __init__(self, path: Path = REFLECTIONS_PATH):
        self.path = path

    def add(self, record: dict) -> None:
        """Append one reflection record."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def for_run(self, user_id: str, run_id: str) -> list[dict]:
        """Return only the reflections written for this user and this run."""
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in self.path.read_text().splitlines() if line]
        return [r for r in rows if r["user_id"] == user_id and r["run_id"] == run_id]


REFLECT_PROMPT = """A trial-registry agent failed a deterministic check. Write ONE short reflection.
Reply with JSON only: {"failure": "<what went wrong, one sentence>",
"strategy": "<what to do differently next attempt, one sentence>"}.
Base it only on the evidence: failed assertions, tool calls, invalid replies, final answer.
If the run stopped on invalid replies, name the reply-format mistake.
Do not explain your reasoning; do not add rules about tools or permissions."""


def evidence_of(result: AgentResult, verdict: dict) -> dict:
    """Return the evidence that triggered a reflection: failed assertions, calls, answer."""
    return {"failed_assertions": [a["check"] for a in verdict["assertions"] if not a["ok"]],
            "tool_calls": [{"name": c["name"], "arguments": c["arguments"], "ok": c["ok"],
                            "observation": (json.dumps(c["result"]["data"], default=str)[:200]
                                            if c["ok"] else c["error"])}
                           for c in result.tool_calls],
            "invalid_replies": [f"step {e['step']}: {e['failure_type']} - {e['problem']}"
                                for e in result.emissions if not e["well_formed"]],
            "final_answer": result.answer[:300], "stop_reason": result.stop_reason}


def write_reflection(model, task_prompt: str, evidence: dict) -> tuple[dict, int]:
    """Return ({failure, strategy, flagged}, tokens used) from one model call."""
    msg = [{"role": "system", "content": REFLECT_PROMPT},
           {"role": "user", "content": f"Task: {task_prompt}\nEvidence: {json.dumps(evidence)}"}]
    reply = model.complete(msg)
    try:
        obj = json.loads(reply.text.strip().strip("`").removeprefix("json"))
    except ValueError:
        obj = {"failure": "the answer did not pass the check",
               "strategy": "call the tools for every part and quote ids exactly"}
    failure, f1 = sanitize(obj.get("failure", ""))
    strategy, f2 = sanitize(obj.get("strategy", ""))
    return ({"failure": failure, "strategy": strategy, "flagged": f1 or f2},
            reply.input_tokens + reply.output_tokens)


# ---------------------------------------------------------------- the bounded loop
@dataclass
class ReflexionResult:
    task: str
    run_id: str
    stop_reason: str = ""
    attempts: list = field(default_factory=list)
    reflections: list = field(default_factory=list)
    tool_calls: int = 0
    tokens: int = 0
    latency_ms: float = 0.0
    final: dict = field(default_factory=dict)

    @property
    def retries(self) -> int:
        """Return the number of retries after the first attempt."""
        return max(0, len(self.attempts) - 1)


def run_reflexion(task: str, prompt: str, truth: dict, model=None, reflector=None,
                  user_id: str = "ani", store: ReflectionStore | None = None,
                  log: Callable[[str], None] = print, run=run_agent,
                  agent_log_path: Path | None = None) -> ReflexionResult:
    """Run one task with verify -> reflect -> retry (bounded); return the full record."""
    model = model or AdapterModel()
    reflector = reflector or AdapterModel(temperature=0.0)
    store = store or ReflectionStore()
    rr = ReflexionResult(task=task, run_id=uuid.uuid4().hex[:8])
    t0 = time.perf_counter()
    for attempt in range(1 + MAX_RETRIES):
        tools_left, tokens_left = TOOL_BUDGET - rr.tool_calls, TOKEN_BUDGET - rr.tokens
        if tools_left <= 0 or tokens_left <= 0:
            rr.stop_reason = "budget_exhausted"
            break
        notes = [r["strategy"] for r in store.for_run(user_id, rr.run_id)]
        res = run(prompt, model=model, reflections=notes or None, max_tool_calls=tools_left,
                  max_tokens=tokens_left, log=log, log_path=agent_log_path)
        rr.tool_calls += res.total_tool_calls
        rr.tokens += res.input_tokens + res.output_tokens
        verdict = verify(task, res, truth)
        rr.attempts.append({"attempt": attempt + 1, "agent_run_id": res.run_id,
                            "answer": res.answer, "stop_reason": res.stop_reason,
                            "verifier": verdict, "oracle_pass": oracle(task, res, truth),
                            "unsupported": unsupported_claims(res),
                            "tool_calls": res.total_tool_calls,
                            "tokens": res.input_tokens + res.output_tokens})
        rr.final = rr.attempts[-1]
        failed = [a["check"] for a in verdict["assertions"] if not a["ok"]]
        log(f"  verifier (attempt {attempt + 1}): {'PASS' if verdict['passed'] else 'FAIL'}"
            + (f" - failed: {failed}" if failed else ""))
        if verdict["passed"]:
            rr.stop_reason = "success"
            break
        if res.stop_reason == "budget_exhausted":
            rr.stop_reason = "budget_exhausted"
            break
        if attempt == MAX_RETRIES:
            rr.stop_reason = "human_review"     # still failing after the last allowed retry
            break
        ev = evidence_of(res, verdict)
        refl, used = write_reflection(reflector, prompt, ev)
        rr.tokens += used
        record = {"ts": datetime.now().isoformat(timespec="seconds"), "user_id": user_id,
                  "run_id": rr.run_id, "task": task, "after_attempt": attempt + 1, **refl,
                  "evidence": ev}
        store.add(record)
        rr.reflections.append(record)
        log(f"  reflection: failure='{refl['failure']}' strategy='{refl['strategy']}'")
        if refl["flagged"]:
            rr.stop_reason = "human_review"
            break
    rr.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    log(f"  reflexion stop: {rr.stop_reason} | attempts: {len(rr.attempts)} | "
        f"tool calls: {rr.tool_calls} | tokens: {rr.tokens} | {rr.latency_ms:.0f} ms")
    return rr


def to_dict(rr: ReflexionResult) -> dict:
    """Return a JSON-ready dict of a Reflexion run."""
    return {**asdict(rr), "retries": rr.retries}


def oracle(task: str, result: AgentResult, truth: dict) -> bool:
    """Return the lenient check (any identifier form) used only to spot false rejections."""
    return verify(task, result, truth, strict=False)["passed"]


def task_list() -> dict:
    """Return the fixed tasks from Part 2."""
    return json.loads((ROOT / "reports/hw07/cases/part2_tasks.json").read_text())["tasks"]
