"""HW9 Part 4: run one question through the Answering and Evaluator agents.

Messages between the agents are plain dicts (printed as JSON). The loop stops after a
PASS or after max_attempts (2), and reports the final answer and evaluation.
"""
from __future__ import annotations

import json
import time

from reference import analyze

MAX_ATTEMPTS = 2


def show(sender: str, receiver: str, message: dict, log) -> None:
    """Return nothing; log one agent-to-agent message."""
    log(f"    {sender:<9}-> {receiver:<9} {json.dumps(message)}")


def run_question(qid: str, question: str, answerer, evaluator, store=None,
                 max_attempts: int = MAX_ATTEMPTS, learn: bool = False,
                 forced_first: str | None = None, log=print) -> dict:
    """Return the full trace of one question: attempts, final result, lessons, latency."""
    if max_attempts not in (1, 2):
        raise ValueError("max_attempts must be 1 or 2")
    t0 = time.perf_counter()
    qtype = analyze(question, answerer.ref)["type"]
    lessons = store.relevant(qtype) if store else []
    log(f"{qid} [{qtype}] {question}")
    for lesson in lessons:
        log(f"    LESSON loaded {lesson['lesson_id']} (use_count={lesson['use_count']}): "
            f"{lesson['correction']}")
    attempts, previous, feedback, created = [], None, None, []
    for n in range(1, max_attempts + 1):
        if n == 1 and forced_first is not None:
            reply = {"answer": forced_first, "lessons_used": [], "checked_reference": False}
            log("    CONTROLLED initial answer (intentionally incomplete)")
        else:
            reply = answerer.answer(question, lessons, previous, feedback)
        show("ANSWERER", "EVALUATOR", {"id": qid, "attempt": n, "answer": reply["answer"]}, log)
        verdict = evaluator.evaluate(question, reply["answer"])
        show("EVALUATOR", "ANSWERER", {"id": qid, "attempt": n, "result": verdict["result"],
                                       "explanation": verdict["explanation"],
                                       "feedback": verdict["feedback"]}, log)
        attempts.append({"attempt": n, **reply, **verdict})
        if n == 1 and verdict["result"] == "REVISE" and learn and store is not None:
            lesson = store.record_failure(verdict["failure_pattern"], qid)
            if lesson:
                created.append(lesson["lesson_id"])
                log(f"    LESSON created {lesson['lesson_id']} from repeated pattern "
                    f"'{lesson['pattern']}' ({', '.join(lesson['learned_from'])})")
        if verdict["result"] == "PASS":
            break
        previous, feedback = reply["answer"], verdict["feedback"]
    latency = round((time.perf_counter() - t0) * 1000, 1)
    final = attempts[-1]
    log(f"    FINAL {final['result']} after {len(attempts)} attempt(s), {latency} ms: "
        f"{final['answer']}")
    return {"id": qid, "question": question, "type": qtype, "attempts": len(attempts),
            "first_result": attempts[0]["result"], "final_result": final["result"],
            "final_answer": final["answer"], "lessons_used": [x["lesson_id"] for x in lessons],
            "lessons_created": created, "latency_ms": latency, "trace": attempts}
