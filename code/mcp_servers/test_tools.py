"""HW5 Part 4 (+ Part 5 III) - offline test runner for execute_tool and run_agent.

Runs with plain asserts, no pytest, no database, no network, no LLM:
the tools get an in-memory FakeStore through dependency injection.
Usage:  python test_tools.py
"""
import json
import sys
from datetime import datetime

from resilience import ResilientStore, RetryPolicy, TransientError
from tool_gateway import execute_tool


class FakeStore:
    """In-memory stand-in for the s3209_rel tables (temporary test fixture)."""
    TRIALS = [
        {"id": 1, "trial_title": "Phase II Study of Drug A in Asthma", "nct_id": "NCT00000001",
         "status": "Recruiting", "enrollment_slots": 40, "sponsor": "Mayo Clinic"},
        {"id": 2, "trial_title": "Phase III Study of Drug B in Migraine", "nct_id": "NCT00000002",
         "status": "Completed", "enrollment_slots": 0, "sponsor": "UCSF Health"},
        {"id": 3, "trial_title": "Phase I Study of Drug C in Asthma", "nct_id": "NCT00000003",
         "status": "Recruiting", "enrollment_slots": 15, "sponsor": "UCSF Health"},
    ]

    def __init__(self):
        self.calls = 0

    def search(self, query, status, limit):
        self.calls += 1
        q = query.lower()
        rows = [t for t in self.TRIALS if q in t["trial_title"].lower() or q in t["sponsor"].lower()]
        if status:
            rows = [t for t in rows if t["status"] == status]
        return rows[:limit]

    def get(self, trial_id):
        self.calls += 1
        return next((dict(t) for t in self.TRIALS if t["id"] == trial_id), None)

    def stats(self, group_by):
        self.calls += 1
        key = "status" if group_by == "status" else "sponsor"
        groups = {}
        for t in self.TRIALS:
            g = groups.setdefault(t[key], {"grp": t[key], "trials": 0, "open_slots": 0})
            g["trials"] += 1
            g["open_slots"] += t["enrollment_slots"]
        return list(groups.values())


class AlwaysDown(FakeStore):
    def get(self, trial_id):
        raise TransientError("database unreachable")


def run(name, inputs, store=None):
    out = execute_tool(name, inputs, store=store or FakeStore())
    assert isinstance(out, str), "execute_tool must return a JSON string"
    env = json.loads(out)
    assert set(env) == {"ok", "data", "error"}, f"bad envelope keys: {set(env)}"
    return env


# ---------------------------------------------------------------- Part 4 tests
def test_search_valid():
    env = run("search_trials", {"query": "asthma", "limit": 5})
    assert env["ok"] is True and env["error"] is None
    assert env["data"]["count"] == 2


def test_search_rejects_short_query():          # Part 3 rejected call #1
    env = run("search_trials", {"query": "a"})
    assert env["ok"] is False and env["data"] is None
    assert "at least 2 characters" in env["error"]


def test_search_rejects_bad_limit():
    env = run("search_trials", {"query": "asthma", "limit": 500})
    assert env["ok"] is False and "limit" in env["error"]


def test_get_valid():
    env = run("get_trial", {"trial_id": 2})
    assert env["ok"] is True and env["data"]["nct_id"] == "NCT00000002"


def test_get_not_found():                       # Part 3 rejected call #2
    env = run("get_trial", {"trial_id": 9999})
    assert env["ok"] is False and env["error"] == "trial 9999 not found"


def test_get_rejects_non_integer():
    env = run("get_trial", {"trial_id": "five"})
    assert env["ok"] is False and "positive integer" in env["error"]


def test_stats_valid():
    env = run("trial_stats", {"group_by": "sponsor"})
    assert env["ok"] is True and env["data"]["total_trials"] == 3


def test_stats_rejects_bad_group():             # Part 3 rejected call #3
    env = run("trial_stats", {"group_by": "color"})
    assert env["ok"] is False and "group_by must be one of" in env["error"]


def test_unknown_tool():
    env = run("drop_tables", {})
    assert env["ok"] is False and "unknown tool" in env["error"]


def test_storage_failure_is_clean():
    store = ResilientStore(AlwaysDown(), RetryPolicy(base_delay_s=0), sleep=lambda s: None)
    env = run("get_trial", {"trial_id": 1}, store=store)
    assert env["ok"] is False and "after 3 attempts" in env["error"]


TESTS = [test_search_valid, test_search_rejects_short_query, test_search_rejects_bad_limit,
         test_get_valid, test_get_not_found, test_get_rejects_non_integer,
         test_stats_valid, test_stats_rejects_bad_group, test_unknown_tool,
         test_storage_failure_is_clean]

try:   # Part 5 III tests are added once the agent exists
    from test_agent import TESTS as AGENT_TESTS
    TESTS += AGENT_TESTS
except ImportError:
    pass


def main():
    stamp = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp()}] RUN: python test_tools.py   (offline: FakeStore, no DB / network / LLM)")
    passed = 0
    for test in TESTS:
        try:
            test()
            passed += 1
            print(f"[{stamp()}] PASS  {test.__name__}")
        except AssertionError as exc:
            print(f"[{stamp()}] FAIL  {test.__name__}: {exc}")
        except Exception as exc:
            print(f"[{stamp()}] FAIL  {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"[{stamp()}] {passed}/{len(TESTS)} tests passed")
    return 0 if passed == len(TESTS) else 1


if __name__ == "__main__":
    sys.exit(main())
