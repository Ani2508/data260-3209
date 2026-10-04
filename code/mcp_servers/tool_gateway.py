"""HW5 Part 4/5 - execute_tool: the ONE safe entry point the agent uses for the 3 domain tools.

execute_tool(name, inputs) -> JSON string with the Part 2B envelope {ok, data, error}.
It never raises: unknown tools, bad inputs, safety-rule violations and storage
failures all come back as {"ok": false, "data": null, "error": "..."}.
"""
from __future__ import annotations

import json
import re

import trials_core as core
from resilience import ResilientStore, RetryExhausted

# ---------------------------------------------------------------- safety rule (Part 5)
# Domain rule: a public trial registry must never receive patient-identifying data.
# Tool inputs that contain an email address, phone number, SSN or medical record
# number (MRN) are blocked before any database call is made.
PHI_PATTERNS = {
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone number": re.compile(r"\b\d{3}[-. ]\d{3}[-. ]\d{4}\b"),
    "medical record number": re.compile(r"\bMRN\s*[:#]?\s*\d+", re.IGNORECASE),
}


def safety_violation(inputs: dict) -> str | None:
    for value in inputs.values():
        if isinstance(value, str):
            for label, pattern in PHI_PATTERNS.items():
                if pattern.search(value):
                    return (f"blocked by safety rule: input contains patient-identifying "
                            f"data ({label}); the trial registry only accepts de-identified queries")
    return None


# ---------------------------------------------------------------- store (injectable)
_default_store = None


def default_store():
    global _default_store
    if _default_store is None:
        _default_store = ResilientStore(core.SQLTrialStore())
    return _default_store


def execute_tool(name: str, inputs: dict | None = None, store=None) -> str:
    """Validate, apply the safety rule, run the tool, and return the envelope as JSON."""
    try:
        if name not in core.TOOLS:
            result = core.fail(f"unknown tool '{name}'; available: {sorted(core.TOOLS)}")
        elif inputs is not None and not isinstance(inputs, dict):
            result = core.fail("inputs must be a JSON object")
        elif (reason := safety_violation(inputs or {})):
            result = core.fail(reason)
        else:
            result = core.TOOLS[name](store or default_store(), dict(inputs or {}))
    except RetryExhausted as exc:
        result = core.fail(str(exc))
    except Exception as exc:  # last line of defence: never crash the agent
        result = core.fail(f"{type(exc).__name__}: {exc}")
    return json.dumps(result, default=str)
