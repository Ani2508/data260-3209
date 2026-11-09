"""HW9 Part 4.2: reusable lessons stored in data/lessons.json.

A lesson is created when the Evaluator reports the same failure pattern twice. Each
lesson keeps lesson_id, failure_pattern, correction, created_at and use_count, plus the
question types it applies to and whether it tells the agent to check the reference data.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

PATTERNS = {
    "omits_current_value": (
        "The answer omits or guesses a changing value (status or enrollment slots).",
        "Check the reference dataset for the current status and enrollment slots before "
        "answering questions about changing values.",
        ["trial_status", "trial_slots"], "check_reference"),
    "omits_requested_value": (
        "The answer does not state the requested catalogue value (sponsor, phase or condition).",
        "Read the catalogue listing and state the requested value in the first sentence.",
        ["trial_sponsor", "trial_other"], "none"),
    "unsupported_claim": (
        "The answer adds numbers or details that are not in the reference record.",
        "State only values from the reference record; leave out guessed counts, dates and "
        "eligibility details.",
        ["trial_status", "trial_slots", "trial_sponsor", "trial_other"], "check_reference"),
    "invents_unknown_trial": (
        "The answer describes a trial id that is not in the reference dataset.",
        "Check the reference dataset first; if the trial id is not there, say it is not "
        "listed and give no status or counts.",
        ["unknown_trial"], "check_reference"),
    "wrong_definition": (
        "The answer's definition of a status or phase differs from the reference.",
        "Use the reference dataset definition of the status or phase.",
        ["definition"], "check_reference"),
    "off_topic_unsupported": (
        "The answer to an off-topic question states catalogue facts.",
        "For questions outside the trial catalogue, say so and mention no trial ids or counts.",
        ["unrelated"], "none"),
}
REPEAT = 2  # a pattern seen this many times becomes a lesson


class LessonStore:
    """Load, select, create and remove lessons (optionally saved to a JSON file)."""

    def __init__(self, path: Path | None = None, lessons: list[dict] | None = None,
                 persist: bool = True) -> None:
        """Return nothing; read lessons from path unless a list is given."""
        self.path = path
        self.persist = persist and path is not None
        if lessons is not None:
            self.lessons = [dict(x) for x in lessons]
        else:
            self.lessons = json.loads(path.read_text()) if path and path.exists() else []
        self.seen: dict[str, list[str]] = {}

    def save(self) -> None:
        """Return nothing; write the lessons to the JSON file when persisting."""
        if self.persist:
            self.path.write_text(json.dumps(self.lessons, indent=2) + "\n")

    def relevant(self, qtype: str) -> list[dict]:
        """Return the lessons for this question type and add 1 to each use_count."""
        chosen = [x for x in self.lessons if qtype in x["applies_to"]]
        for lesson in chosen:
            lesson["use_count"] += 1
        if chosen:
            self.save()
        return chosen

    def record_failure(self, pattern: str | None, question_id: str) -> dict | None:
        """Return a new lesson when this failure pattern repeats, else None."""
        if not pattern or pattern not in PATTERNS:
            return None
        self.seen.setdefault(pattern, []).append(question_id)
        if len(self.seen[pattern]) < REPEAT or any(x["pattern"] == pattern
                                                  for x in self.lessons):
            return None
        failure, correction, applies_to, action = PATTERNS[pattern]
        lesson = {"lesson_id": f"lesson_{len(self.lessons) + 1:03d}",
                  "failure_pattern": failure, "correction": correction,
                  "created_at": date.today().isoformat(), "use_count": 0,
                  "pattern": pattern, "applies_to": applies_to, "action": action,
                  "learned_from": list(self.seen[pattern])}
        self.lessons.append(lesson)
        self.save()
        return lesson

    def remove(self, lesson_id: str) -> None:
        """Return nothing; drop one lesson (used when validation finds a regression)."""
        self.lessons = [x for x in self.lessons if x["lesson_id"] != lesson_id]
        self.save()
