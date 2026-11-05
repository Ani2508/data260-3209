"""Offline tests for HW9 Part 1 (no Redis, no MySQL): python3 code/cache/test_trial_cache.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trial_cache import TrialCache, views_key  # noqa: E402


class FakeRedis:
    """In-memory stand-in for the two Redis commands the counter uses."""

    def __init__(self) -> None:
        """Return nothing; start with an empty key space."""
        self.data: dict[str, int] = {}

    def incr(self, key: str) -> int:
        """Return the value of key after adding one."""
        self.data[key] = self.data.get(key, 0) + 1
        return self.data[key]

    def get(self, key: str) -> str | None:
        """Return the stored value as text, or None."""
        return str(self.data[key]) if key in self.data else None


def run_tests() -> int:
    """Return the number of passed tests (raises AssertionError on the first failure)."""
    saved: list[tuple[int, int]] = []

    def fake_save(trial_id: int, count: int) -> int:
        saved.append((trial_id, count))
        return 1

    cache = TrialCache(FakeRedis(), save_views=fake_save)

    # 1. key uses the PREFIX
    assert views_key(7) == "s3209:views:trial:7"

    # 2. every access returns the running total
    totals = [cache.increment_trial_views(7) for _ in range(25)]
    assert totals == list(range(1, 26))

    # 3. MySQL is written only at 10 and 20
    assert saved == [(7, 10), (7, 20)]

    # 4. counters are separate per trial
    assert cache.increment_trial_views(8) == 1 and cache.get_trial_views(7) == 25

    # 5. edge case: bad ids fail fast and do not touch Redis
    for bad in (0, -3, "7", True):
        try:
            cache.increment_trial_views(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted bad id {bad!r}")

    # 6. edge case: a sync for a missing trial raises
    missing = TrialCache(FakeRedis(), save_views=lambda t, c: 0, sync_every=1)
    try:
        missing.increment_trial_views(999)
    except ValueError:
        pass
    else:
        raise AssertionError("missing trial was not reported")
    return 6


if __name__ == "__main__":
    print(f"HW9 Part 1 offline tests: {run_tests()} / 6 passed")
