"""HW5 Part 5 III - two extra offline tests (added to the Part 4 runner in test_tools.py)."""
import json
import tempfile
from pathlib import Path

from agent import MockModel, run_agent
from tool_gateway import execute_tool


def test_safety_rule_blocks_patient_data():
    from test_tools import FakeStore
    store = FakeStore()
    env = json.loads(execute_tool("search_trials",
                                  {"query": "asthma trial for john.doe@gmail.com"}, store=store))
    assert env["ok"] is False and env["data"] is None
    assert env["error"].startswith("blocked by safety rule")
    assert store.calls == 0, "blocked call must never reach the data store"


def test_agent_stops_at_max_steps():
    from test_tools import FakeStore
    always_tool = MockModel([{"content": "", "tool_calls": [
        {"name": "get_trial", "arguments": {"trial_id": 1}}]}])
    log = Path(tempfile.mkdtemp()) / "agent_runs.jsonl"
    out = run_agent("loop forever", model=always_tool, max_steps=3,
                    execute=lambda n, i: execute_tool(n, i, store=FakeStore()), log_path=log)
    assert out["stop_reason"] == "max_steps"
    assert out["steps"] == 3 and out["tool_calls"] == 3
    events = [json.loads(line)["event"] for line in log.read_text().splitlines()]
    assert events == ["start", "tool_call", "tool_call", "tool_call", "stop"]


TESTS = [test_safety_rule_blocks_patient_data, test_agent_stops_at_max_steps]
