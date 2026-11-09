"""HW9 Part 4: Answering Agent and Evaluator Agent.

Answering Agent: llama3.1:8b through src/model_client.py. It sees the public catalogue
listing; lessons can tell it to check the reference dataset; on a revision it also gets
the Evaluator's feedback.
Evaluator Agent: checks every answer against reference_data.json (ground truth) and
returns PASS or REVISE with an explanation, feedback and a failure pattern.
"""
from __future__ import annotations

import json
import re

from reference import analyze, catalogue_entry, norm, reference_block

ANSWER_SYSTEM = (
    "You are the Answering Agent for the s3209 clinical trial catalogue help desk. "
    "Answer the coordinator's question in 1-3 plain sentences. Use the catalogue listing "
    "and any reference facts given. Never invent trial IDs. "
    'Reply only with JSON: {"answer": "..."}')
JUDGE_SYSTEM = (
    "You are the Evaluator Agent. Compare the answer's definition with the reference "
    "definition. Pass it if it means the same thing and does not contradict it. "
    'Reply only with JSON: {"pass": true or false, "reason": "one short sentence"}')
NOT_LISTED = re.compile(
    r"not (listed|found|in (the|our) (catalog|catalogue|reference|dataset|records?)|available"
    r"|recogni[sz]ed)|no (record|entry|information|listing)|(does|do) not (exist|appear)"
    r"|isn t listed|(cannot|could not|couldn t|unable to) (find|locate)")
LABEL = {"status": "status", "enrollment_slots": "enrollment slots", "sponsor": "sponsor",
         "phase": "phase", "condition": "condition"}


def ask_json(llm, system: str, user: str, key: str) -> dict:
    """Return the model's JSON reply; fall back to {key: raw text} if it is not JSON."""
    text = llm.complete([{"role": "system", "content": system},
                         {"role": "user", "content": user}]).text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else text)
    except ValueError:
        data = {}
    if not isinstance(data, dict) or key not in data:
        return {key: text}
    return data


class AnsweringAgent:
    """Answers questions; uses lessons and evaluator feedback when given."""

    def __init__(self, llm, ref: dict) -> None:
        """Return nothing; keep the model client and the reference dataset."""
        self.llm = llm
        self.ref = ref

    def answer(self, question: str, lessons: list[dict] | None = None,
               previous: str | None = None, feedback: str | None = None) -> dict:
        """Return {'answer', 'lessons_used', 'checked_reference'} for one attempt."""
        info = analyze(question, self.ref)
        parts = [f"Question: {question}"]
        if info["known"]:
            parts.append("Catalogue listing:\n" + "\n".join(catalogue_entry(r)
                                                             for r in info["known"]))
        lessons = lessons or []
        checked = any(lesson.get("action") == "check_reference" for lesson in lessons)
        if lessons:
            parts.append("Lessons from earlier mistakes:\n" + "\n".join(
                f"- {x['lesson_id']}: {x['failure_pattern']} Correction: {x['correction']}"
                for x in lessons))
        if checked:
            parts.append("Reference dataset check:\n" + reference_block(info, self.ref))
        if feedback:
            parts.append(f"Your previous answer: {previous}\nEvaluator feedback: {feedback}\n"
                         "Write a corrected answer that follows the feedback.")
        reply = ask_json(self.llm, ANSWER_SYSTEM, "\n\n".join(parts), "answer")
        return {"answer": str(reply["answer"]).strip(),
                "lessons_used": [x["lesson_id"] for x in lessons], "checked_reference": checked}


UNSTATED = re.compile(r" (not|n t) (specif|list|mention|provid|given|stated|includ)\w*"
                      r"| (no|without) (information|data|details) | unspecified ")
NEGATED = re.compile(r" (not|no longer|isn t|aren t)( \w+){0,2} recruiting ")


def has_value(answer: str, field: str, rec: dict) -> bool:
    """Return True if the answer states the record's value for the field."""
    a = f" {norm(answer)} "
    value = rec[field]
    if field == "enrollment_slots" and (UNSTATED.search(a) or " specified " in a):
        return False  # "no slots specified" means the value is unknown, not 0
    if field == "enrollment_slots":
        return bool(re.search(rf" {value} ", a)) or (value == 0 and bool(
            re.search(r" (zero|no) (open |available |enrollment )*(slots|spots|places) ", a)))
    if field == "status":
        status = norm(value)
        if status == "active not recruiting":
            return " not recruiting " in a and " active " in a
        if status == "recruiting":
            return " recruiting " in a and not NEGATED.search(a)
        return f" {status[:6]}" in a  # complet / termin
    if field == "phase":
        return f" {norm(value)} " in a
    return norm(value) in a


def unsupported_numbers(answer: str, question: str, info: dict) -> list[str]:
    """Return numbers in the answer that are not in the question or the reference records."""
    allowed = set(re.findall(r"\d+", NCT_STRIP.sub(" ", question))) | {"1", "2", "3", "4"}
    for rec in info["known"]:
        allowed |= {str(rec["enrollment_slots"])} | set(re.findall(r"\d+", rec["title"]))
    found = re.findall(r"\d+", NCT_STRIP.sub(" ", answer))
    return sorted({n for n in found if n not in allowed})


NCT_STRIP = re.compile(r"NCT\d{8}", re.IGNORECASE)


class EvaluatorAgent:
    """Checks answers against the reference dataset (the ground truth)."""

    def __init__(self, llm, ref: dict) -> None:
        """Return nothing; keep the model client (used for definitions) and the reference."""
        self.llm = llm
        self.ref = ref

    def evaluate(self, question: str, answer: str) -> dict:
        """Return {'result', 'explanation', 'feedback', 'failure_pattern'} for one answer."""
        info = analyze(question, self.ref)
        qtype = info["type"]
        if qtype == "unknown_trial":
            return self._unknown(info, answer)
        if qtype == "definition":
            return self._definition(info, answer)
        if qtype == "unrelated":
            if NCT_STRIP.search(answer) or "enrollment slot" in answer.lower():
                return revise("The answer states catalogue facts for an off-topic question.",
                              "Say the question is outside the trial catalogue and mention no "
                              "trial ids or counts.", "off_topic_unsupported")
            return passed("The question is outside the catalogue and the answer states no "
                          "catalogue facts.")
        rec, field = info["known"][0], info["field"] or "status"
        label = LABEL.get(field, field)
        if not has_value(answer, field, rec):
            pattern = ("omits_current_value" if field in ("status", "enrollment_slots")
                       else "omits_requested_value")
            return revise(f"The answer does not state the {label} of {rec['nct_id']}.",
                          f"Reference dataset: {rec['nct_id']} {label} is {rec[field]}. "
                          "State this value directly.", pattern)
        extra = unsupported_numbers(answer, question, info)
        if extra:
            return revise(f"The answer gives numbers not in the reference record: "
                          f"{', '.join(extra)}.",
                          "Keep only values from the reference record: "
                          + reference_block(info, self.ref), "unsupported_claim")
        return passed(f"The answer states {label} = {rec[field]}, matching the reference "
                      "dataset.")

    def _unknown(self, info: dict, answer: str) -> dict:
        """Return the evaluation for a question about a trial id that is not listed."""
        nct = info["unknown"][0]
        if NOT_LISTED.search(norm(answer)) and not unsupported_numbers(answer, "", info):
            return passed(f"{nct} is not in the reference dataset and the answer says so.")
        return revise(f"{nct} is not in the reference dataset, but the answer does not say so.",
                      f"Say that {nct} is not listed in the catalogue and give no status or "
                      "counts.", "invents_unknown_trial")

    def _definition(self, info: dict, answer: str) -> dict:
        """Return the evaluation for a definition question (model judge vs reference)."""
        term = info["term"]
        definition = self.ref["definitions"][term]
        verdict = ask_json(self.llm, JUDGE_SYSTEM, f"Term: {term}\nReference definition: "
                           f"{definition}\nAnswer: {answer}", "pass")
        reason = str(verdict.get("reason", "")).strip() or "No reason given."
        if verdict.get("pass") is True:
            return passed(f"Matches the reference definition of {term}. {reason}")
        return revise(f"The definition differs from the reference. {reason}",
                      f"Reference definition of {term}: {definition}", "wrong_definition")


def passed(explanation: str) -> dict:
    """Return a PASS evaluation."""
    return {"result": "PASS", "explanation": explanation, "feedback": "",
            "failure_pattern": None}


def revise(explanation: str, feedback: str, pattern: str) -> dict:
    """Return a REVISE evaluation with feedback and the failure pattern."""
    return {"result": "REVISE", "explanation": explanation, "feedback": feedback,
            "failure_pattern": pattern}
