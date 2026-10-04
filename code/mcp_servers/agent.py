"""HW5 Part 5 - agent loop: local Ollama model + the 3 domain tools via execute_tool.

run_agent(user_input) asks the model, runs any tool calls through execute_tool,
feeds the results back, and repeats until the model answers, a safety rule
blocks a call, or max_steps is reached. Every step is logged to agent_runs.jsonl.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

import trials_core as core
from tool_gateway import execute_tool

SEED = 3209
DEFAULT_MAX_STEPS = 6
LOG_PATH = Path(__file__).resolve().parents[2] / "reports" / "hw05" / "raw" / "agent_runs.jsonl"

SYSTEM_PROMPT = (
    "You are an assistant for a public clinical-trial registry (database s3209_rel). "
    "Use the tools to answer questions about trials and sponsors; never invent data. "
    "Call exactly one tool per step and wait for its result before the next call; use ids that "
    "appear in earlier tool results. Leave optional arguments out instead of sending null. "
    "When you have enough information, answer briefly in plain text. "
    "If a tool returns ok=false, explain the error to the user instead of retrying the same call."
)

TOOL_SPECS = [{"type": "function",
               "function": {"name": name, "description": spec["description"],
                            "parameters": spec["input_schema"]}}
              for name, spec in core.TOOL_SCHEMAS.items()]


# ---------------------------------------------------------------- models
class OllamaModel:
    """Local model through the Ollama server (default llama3.1:8b, temperature 0, fixed seed)."""

    def __init__(self, model: str | None = None):
        import ollama
        self.client = ollama
        self.name = model or os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    def chat(self, messages: list[dict]) -> dict:
        resp = self.client.chat(model=self.name, messages=messages, tools=TOOL_SPECS,
                                options={"temperature": 0, "seed": SEED})
        msg = resp["message"]
        calls = [{"name": c["function"]["name"], "arguments": dict(c["function"]["arguments"] or {})}
                 for c in (msg.get("tool_calls") or [])]
        return {"content": msg.get("content") or "", "tool_calls": calls}


class MockModel:
    """Offline stand-in for tests: replays scripted replies (the last one repeats forever)."""

    def __init__(self, replies: list[dict]):
        self.replies, self.i, self.name = replies, 0, "MockModel"

    def chat(self, messages: list[dict]) -> dict:
        reply = self.replies[min(self.i, len(self.replies) - 1)]
        self.i += 1
        return reply


# ---------------------------------------------------------------- helpers
def _coerce(name: str, args: dict) -> dict:
    """Clean up small-model argument mistakes using the tool schema:
    numbers sent as strings ("5") become ints, and optional fields sent as
    "null" / "None" / "" are dropped so the tool default applies."""
    schema = core.TOOL_SCHEMAS.get(name, {}).get("input_schema", {})
    props, required = schema.get("properties", {}), set(schema.get("required", []))
    out = {}
    for key, value in args.items():
        if key not in required and (value is None or
                                    (isinstance(value, str) and value.strip().lower() in ("", "null", "none"))):
            continue
        if props.get(key, {}).get("type") == "integer" and isinstance(value, str) \
                and value.strip().lstrip("-").isdigit():
            value = int(value)
        out[key] = value
    return out


def _text_tool_call(content: str) -> list[dict]:
    """llama3.1 sometimes writes the tool call as JSON text instead of a real tool call."""
    text = content.strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return []
    try:
        obj = json.loads(text[start:end + 1])
    except ValueError:
        return []
    if isinstance(obj, dict) and obj.get("name") in core.TOOLS:
        args = obj.get("parameters", obj.get("arguments", {}))
        return [{"name": obj["name"], "arguments": args if isinstance(args, dict) else {}}]
    return []


class RunLogger:
    def __init__(self, path: Path, run_id: str, user_input: str, model_name: str):
        self.path, self.run_id = path, run_id
        path.parent.mkdir(parents=True, exist_ok=True)
        self.write({"event": "start", "user_input": user_input, "model": model_name})

    def write(self, record: dict) -> None:
        record = {"run_id": self.run_id,
                  "ts": datetime.now().isoformat(timespec="milliseconds"), **record}
        with open(self.path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")


# ---------------------------------------------------------------- the loop
def run_agent(user_input: str, model=None, max_steps: int = DEFAULT_MAX_STEPS,
              execute: Callable[[str, dict], str] = execute_tool,
              log_path: Path = LOG_PATH) -> dict:
    model = model or OllamaModel()
    run_id = uuid.uuid4().hex[:8]
    log = RunLogger(Path(log_path), run_id, user_input, model.name)
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}]
    step, tool_calls, answer, stop_reason = 0, 0, "", None
    t0 = time.perf_counter()

    while stop_reason is None:
        if step >= max_steps:                       # turn counter ceiling
            stop_reason = "max_steps"
            answer = f"Stopped after {max_steps} steps without a final answer."
            break
        step += 1
        reply = model.chat(messages)
        calls = reply["tool_calls"] or _text_tool_call(reply["content"])
        if len(calls) > 1:                          # enforce one tool call per step
            log.write({"event": "note", "step": step,
                       "note": f"model asked for {len(calls)} calls; running only the first"})
            calls = calls[:1]

        if not calls:                 # model answered -> normal completion
            answer = reply["content"].strip()
            log.write({"event": "final_answer", "step": step, "answer": answer})
            stop_reason = "final_answer"
            break

        messages.append({"role": "assistant", "content": "",
                         "tool_calls": [{"function": {"name": c["name"], "arguments": c["arguments"]}}
                                        for c in calls]})
        for call in calls:
            tool_calls += 1
            args = _coerce(call["name"], call["arguments"])
            result = execute(call["name"], args)
            env = json.loads(result)
            log.write({"event": "tool_call", "step": step, "tool": call["name"],
                       "input": args, "ok": env["ok"], "result": env})
            messages.append({"role": "tool", "content": result, "tool_name": call["name"]})
            if not env["ok"] and str(env["error"]).startswith("blocked by safety rule"):
                stop_reason = "safety_block"
                answer = ("I can't run that request: " + env["error"] +
                          ". Please remove personal patient details and ask again.")
                break

    elapsed = round(time.perf_counter() - t0, 2)
    summary = {"run_id": run_id, "user_input": user_input, "model": model.name,
               "steps": step, "tool_calls": tool_calls, "stop_reason": stop_reason,
               "max_steps": max_steps, "seconds": elapsed, "answer": answer}
    log.write({"event": "stop", **{k: v for k, v in summary.items() if k != "run_id"}})
    return summary


if __name__ == "__main__":
    import sys
    print(json.dumps(run_agent(" ".join(sys.argv[1:]) or "How many trials are recruiting?"), indent=2))
