"""HW9 Part 1 demo: 25 accesses of one trial through the Redis view counter.

Needs Redis (make hw09-redis-up) and MySQL s3209_rel with trials.view_count
(make hw09-migrate).   Run: python3 code/run_hw09_part1.py [--trial-id N] [--n 25]
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import redis
from sqlalchemy import text

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "cache"))
sys.path.insert(0, str(ROOT / "web_application"))

from database import engine  # noqa: E402
from trial_cache import REDIS_URL, TrialCache, views_key  # noqa: E402

RUN_BY = "Ani Taraiya"


class PendingLog(logging.Handler):
    """Hold cache log messages so each one prints after its "Access #n" line."""

    def __init__(self) -> None:
        """Return nothing; start with no pending messages."""
        super().__init__(logging.INFO)
        self.pending: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Return nothing; keep the message until the access line is printed."""
        self.pending.append(record.getMessage())

    def flush_after_access(self) -> None:
        """Return nothing; print and clear the pending messages."""
        for message in self.pending:
            print(f"✓ {message}")
        self.pending.clear()


def pick_trial(trial_id: int | None) -> tuple[int, str, str]:
    """Return (id, nct_id, trial_title) of the requested trial, or of the lowest id."""
    sql = "SELECT id, nct_id, trial_title FROM trials "
    sql += "WHERE id = :tid" if trial_id else "ORDER BY id LIMIT 1"
    with engine.connect() as conn:
        row = conn.execute(text(sql), {"tid": trial_id}).first()
    if row is None:
        raise SystemExit(f"No trial found (trial_id={trial_id}). Seed the trials table first.")
    return int(row[0]), row[1], row[2]


def db_view_count(trial_id: int) -> int:
    """Return trials.view_count for one trial as stored in MySQL."""
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT view_count FROM trials WHERE id = :tid"),
                                {"tid": trial_id}).scalar_one())


def main() -> None:
    """Return nothing; run the counter demo and print the expected output."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-id", type=int, default=None)
    parser.add_argument("--n", type=int, default=25)
    args = parser.parse_args()

    handler = PendingLog()
    cache_logger = logging.getLogger("s3209.trial_cache")
    cache_logger.addHandler(handler)
    cache_logger.setLevel(logging.INFO)

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    trial_id, nct_id, title = pick_trial(args.trial_id)
    key = views_key(trial_id)

    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"Redis {client.info('server')['redis_version']} at {REDIS_URL}")
    print(f"Trial id={trial_id} {nct_id} '{title}'   key={key}")
    client.delete(key)
    with engine.begin() as conn:
        conn.execute(text("UPDATE trials SET view_count = 0 WHERE id = :tid"), {"tid": trial_id})
    print(f"Reset: Redis {key} deleted, MySQL view_count = 0\n")

    cache = TrialCache(client)
    print("=== Testing Counter ===")
    for i in range(1, args.n + 1):
        total = cache.increment_trial_views(trial_id)
        print(f"Access #{i}: Total = {total}")
        handler.flush_after_access()

    print(f"\nRedis GET {key} = {cache.get_trial_views(trial_id)}")
    print(f"MySQL trials.view_count (id={trial_id}) = {db_view_count(trial_id)}"
          f"   (last sync at {args.n // 10 * 10})")


if __name__ == "__main__":
    main()
