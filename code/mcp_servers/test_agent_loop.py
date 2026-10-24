"""HW7 Part 2 - offline tests for agent_loop (no model, no database, no network).

Usage:  python code/mcp_servers/test_agent_loop.py
"""
import json
from dataclasses import dataclass

from agent_loop import parse_reply, run_agent, validate_args
from test_tools import FakeStore
from tool_gateway import execute_tool


@dataclass
class Reply:
    text: str
    input_tokens: int = 10
    output_tokens: int = 5


class ScriptedModel:
    """Replays fixed replies (the last one repeats)."""
    name = "scripted"

    def __init__(self, *texts):
        self.texts, self.i = list(texts), 0

    def complete(self, messages):
        text = self.texts[min(self.i, len(self.texts) - 1)]
        self.i += 1
        return Reply(text)


def fake_execute(name, args):
    return execute_tool(name, args, store=FakeStore())


def run(*texts, **kw):
    return run_agent("test task", model=ScriptedModel(*texts), execute=fake_execute,
                     log=lambda s: None, log_path=None, **kw)


def test_two_step_chain():
    r = run('{"tool": "search_trials", "arguments": {"query": "Asthma"}}',
            '{"tool": "get_trial", "arguments": {"trial_id": 1}}',
            '{"final_answer": "Trial 1 is Recruiting."}')
    assert r.stop_reason == "final_answer" and r.total_tool_calls == 2
    assert [c["name"] for c in r.tool_calls] == ["search_trials", "get_trial"]
    assert r.repairs == 0


def test_unknown_tool_is_repaired_once():
    r = run('{"tool": "find_trial", "arguments": {}}',
            '{"tool": "get_trial", "arguments": {"trial_id": 2}}',
            '{"final_answer": "done"}')
    assert r.emissions[0]["failure_type"] == "unknown_tool"
    assert r.repairs == 1 and r.stop_reason == "final_answer"


def test_malformed_arguments_detected():
    a = parse_reply('{"tool": "get_trial", "arguments": {"trial_id": "five"}}')
    assert a.kind == "invalid" and a.failure_type == "malformed_arguments"
    assert "integer" in a.problem


def test_text_when_tool_required():
    r = run("There are many trials.", '{"final_answer": "x"}', '{"final_answer": "x"}')
    assert r.emissions[0]["failure_type"] == "text_when_tool_required"
    assert r.stop_reason == "repair_limit"          # bounded: never loops forever


def test_hard_ceiling():
    r = run('{"tool": "trial_stats", "arguments": {}}', max_steps=3)
    assert r.stop_reason == "max_steps" and r.steps == 3


def test_nonexistent_id_does_not_crash():
    r = run('{"tool": "get_trial", "arguments": {"trial_id": 99999}}',
            '{"final_answer": "Trial 99999 does not exist."}')
    assert r.tool_calls[0]["ok"] is False and "not found" in r.tool_calls[0]["error"]
    assert r.stop_reason == "final_answer"


def test_code_fence_and_schema():
    assert parse_reply('```json\n{"final_answer": "ok"}\n```').kind == "final"
    assert validate_args("search_trials", {"query": "a"}) == ["'query' needs at least 2 characters"]
    assert validate_args("trial_stats", {"group_by": "year"})


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(json.dumps({"passed": len(tests)}))
