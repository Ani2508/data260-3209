"""Offline tests for HW9 Part 4 (fake model, no Ollama):
python3 code/self_improving/test_self_improving.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import AnsweringAgent, EvaluatorAgent, has_value  # noqa: E402
from lessons import LessonStore  # noqa: E402
from reference import analyze, load_json  # noqa: E402
from system import run_question  # noqa: E402


class Reply:
    """Model reply holder with a .text attribute like CompletionResult."""

    def __init__(self, text: str) -> None:
        """Return nothing; keep the text."""
        self.text = text


class FakeLLM:
    """Answers from feedback or the reference check, otherwise says it does not know."""

    def complete(self, messages: list[dict]) -> Reply:
        """Return a JSON reply chosen from the prompt content."""
        user = messages[-1]["content"]
        if "Reference definition" in user:
            return Reply(json.dumps({"pass": True, "reason": "same meaning"}))
        if "Evaluator feedback:" in user:
            return Reply(json.dumps({"answer": user.split("Evaluator feedback:")[1]
                                     .split("Write a corrected")[0].strip()}))
        if "Reference dataset check:" in user:
            return Reply(json.dumps({"answer": user.split("Reference dataset check:\n")[1]
                                     .split("\n")[0]}))
        return Reply(json.dumps({"answer": "I do not have the current details for that."}))


def run_tests() -> int:
    """Return the number of passed tests (raises AssertionError on the first failure)."""
    ref = load_json("reference_data.json")
    llm = FakeLLM()
    answerer, evaluator = AnsweringAgent(llm, ref), EvaluatorAgent(llm, ref)
    quiet = lambda *_: None  # noqa: E731

    # 1. question types
    kinds = [analyze(q, ref)["type"] for q in (
        "How many enrollment slots does trial NCT72283365 have?",
        "Can I still enroll in trial NCT48236558?", "What is the status of trial NCT11111111?",
        "What does a Terminated status mean?", "What is the capital of France?")]
    assert kinds == ["trial_slots", "trial_status", "unknown_trial", "definition", "unrelated"]

    # 2-3. value checks (edge cases: "not recruiting" and zero slots)
    rec = next(t for t in ref["trials"] if t["nct_id"] == "NCT48236558")
    assert has_value("It is recruiting now.", "status", rec)
    assert not has_value("It is no longer recruiting.", "status", rec)
    assert not has_value("No, it is not currently recruiting.", "status", rec)
    zero = next(t for t in ref["trials"] if t["nct_id"] == "NCT30565986")
    assert has_value("There are no open enrollment slots.", "enrollment_slots", zero)
    assert not has_value("It has no enrollment slots specified in the catalog.",
                         "enrollment_slots", zero)

    # 4. evaluator: missing value -> REVISE with the reference value in the feedback
    q = "How many enrollment slots does trial NCT72283365 have?"
    bad = evaluator.evaluate(q, "Please check with the sponsor.")
    assert bad["result"] == "REVISE" and "114" in bad["feedback"]
    assert bad["failure_pattern"] == "omits_current_value"

    # 5. evaluator: unsupported number -> REVISE
    extra = evaluator.evaluate(q, "Trial NCT72283365 has 114 slots and closes in 2027.")
    assert extra["failure_pattern"] == "unsupported_claim"

    # 6. unknown trial and unrelated questions
    assert evaluator.evaluate("What is the status of trial NCT11111111?",
                              "NCT11111111 is not listed in our catalogue.")["result"] == "PASS"
    assert evaluator.evaluate("What is the capital of France?", "Paris.")["result"] == "PASS"

    # 7. revision loop: forced bad first answer, feedback fixes it, stops at 2 attempts
    t = run_question("D", "What is the current status of trial NCT48236558?", answerer,
                     evaluator, None, 2, forced_first="It is a hypertension study.", log=quiet)
    assert t["first_result"] == "REVISE" and t["final_result"] == "PASS" and t["attempts"] == 2

    # 8-9. lesson created after the 2nd repeated failure, then loaded and reused
    store = LessonStore(lessons=[], persist=False)
    first = run_question("A", "What is the current status of trial NCT10856964?", answerer,
                         evaluator, store, 2, learn=True, log=quiet)
    second = run_question("B", q, answerer, evaluator, store, 2, learn=True, log=quiet)
    assert first["lessons_created"] == [] and second["lessons_created"] == ["lesson_001"]
    later = run_question("C", "Is trial NCT75969695 open for enrollment?", answerer, evaluator,
                         store, 2, learn=True, log=quiet)
    assert later["lessons_used"] == ["lesson_001"] and later["first_result"] == "PASS"
    assert store.lessons[0]["use_count"] == 1
    assert set(store.lessons[0]) >= {"lesson_id", "failure_pattern", "correction",
                                     "created_at", "use_count"}

    # 10. edge case: empty question fails fast
    try:
        analyze("  ", ref)
    except ValueError:
        pass
    else:
        raise AssertionError("empty question accepted")
    return 10


if __name__ == "__main__":
    print(f"HW9 Part 4 offline tests: {run_tests()} / 10 passed")
