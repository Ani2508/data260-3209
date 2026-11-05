"""Offline tests for HW9 Part 2 (no Redis, Kafka, MySQL or model):
python3 code/semantic_cache/test_semantic_cache.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "kafka_agents"))

from qa_service import QAService  # noqa: E402
from semantic_cache import similarity_from_distance  # noqa: E402
from trial_facts import data_version, extract_nct_ids, facts_text  # noqa: E402


class FakeEmbedder:
    """Returns a fixed 2-value vector; similarity is decided by FakeCache."""

    def encode(self, text: str) -> bytes:
        """Return 8 bytes standing in for a 2-dim FLOAT32 vector."""
        return b"\x00" * 8


class FakeCache:
    """Exact-text cache: similarity 1.0 for a stored query, else 0.3 to the last entry."""

    def __init__(self) -> None:
        """Return nothing; start empty with threshold 0.85."""
        self.threshold = 0.85
        self.entries: list[dict] = []
        self.next_query = ""

    def nearest(self, vec: bytes) -> dict | None:
        """Return the best entry for next_query, or None when empty."""
        if not self.entries:
            return None
        for e in self.entries:
            if e["query"] == self.next_query:
                return {**e, "similarity": 1.0}
        return {**self.entries[-1], "similarity": 0.3}

    def store(self, query, vec, answer, version, trial_ids, review="") -> str:
        """Return a fake key after keeping the entry."""
        self.entries.append({"query": query, "answer": answer, "data_version": version,
                             "review": review})
        return f"s3209:semcache:{len(self.entries)}"


class FakePipeline:
    """Counts agent runs and returns an approved answer."""

    def __init__(self) -> None:
        """Return nothing; no calls yet."""
        self.calls = 0

    def ask(self, question: str, facts: str = "") -> dict:
        """Return a final message like the HW8 Reviewer's."""
        self.calls += 1
        return {"status": "approved", "answer": f"answer {self.calls}"}


def run_tests() -> int:
    """Return the number of passed tests (raises AssertionError on the first failure)."""
    # 1-2. cosine distance -> similarity
    assert similarity_from_distance("0.05") == 0.95
    assert similarity_from_distance(0) == 1.0

    # 3. NCT ids: case-insensitive, de-duplicated, ordered
    assert extract_nct_ids("status of nct12345678 and NCT87654321 vs NCT12345678?") == [
        "NCT12345678", "NCT87654321"]

    # 4. edge case: no ids / empty input
    assert extract_nct_ids("") == [] and extract_nct_ids("trial NCT123") == []

    # 5. data-version marker
    row = {"id": 4, "nct_id": "NCT12345678", "trial_title": "T", "status": "Completed",
           "enrollment_slots": 0, "sponsor": "S", "updated_at": datetime(2026, 11, 4, 16, 5, 9)}
    version = data_version([row])
    assert version.startswith("4@") and len(version) == 10 and data_version([]) == "none"
    # view syncs touch updated_at only, so the version must not change
    assert data_version([{**row, "updated_at": datetime(2027, 1, 1)}]) == version
    assert data_version([{**row, "status": "Terminated"}]) != version
    assert "status Completed" in facts_text([row])

    # 6-7. miss runs the agents and stores; the same question then hits without the agents
    cache, pipe = FakeCache(), FakePipeline()
    qa = QAService(cache, FakeEmbedder(), pipe)
    q = "What should a patient check before joining a trial?"
    cache.next_query = q
    first = qa.answer(q)
    assert first["is_cached"] is False and pipe.calls == 1 and len(cache.entries) == 1
    second = qa.answer(q)
    assert second["is_cached"] is True and second["similarity"] == 1.0
    assert second["answer"] == first["answer"] and pipe.calls == 1

    # 8. below-threshold match is a miss
    cache.next_query = "unrelated"
    assert qa.answer("unrelated")["is_cached"] is False and pipe.calls == 2

    # 9. edge case: empty question fails fast
    try:
        qa.answer("  ")
    except ValueError:
        pass
    else:
        raise AssertionError("empty question accepted")
    return 9


if __name__ == "__main__":
    print(f"HW9 Part 2 offline tests: {run_tests()} / 9 passed")
