"""HW9 Part 1: Redis-backed view counter for the primary entity (Trial).

Every access increments a Redis counter with INCR. Every SYNC_EVERY increments the
current count is written to the MySQL trials.view_count column, so MySQL is updated
once per 10 views instead of on every view.
"""
from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from pathlib import Path

PREFIX = "s3209"
SYNC_EVERY = 10
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
WEB_APP = Path(__file__).resolve().parents[1] / "web_application"

logger = logging.getLogger(f"{PREFIX}.trial_cache")


def views_key(trial_id: int) -> str:
    """Return the Redis key that holds the view count of one trial."""
    if not isinstance(trial_id, int) or isinstance(trial_id, bool) or trial_id <= 0:
        raise ValueError(f"trial_id must be a positive integer, got {trial_id!r}")
    return f"{PREFIX}:views:trial:{trial_id}"


def save_views_to_db(trial_id: int, count: int) -> int:
    """Return the number of MySQL rows updated after writing count to trials.view_count."""
    if str(WEB_APP) not in sys.path:
        sys.path.insert(0, str(WEB_APP))
    from database import SessionLocal
    from models import Trial

    db = SessionLocal()
    try:
        rows = (db.query(Trial).filter(Trial.id == trial_id)
                .update({Trial.view_count: count}, synchronize_session=False))
        db.commit()
        return rows
    finally:
        db.close()


class TrialCache:
    """Redis cache in front of the trials table."""

    def __init__(self, redis_client, save_views: Callable[[int, int], int] | None = None,
                 sync_every: int = SYNC_EVERY) -> None:
        """Return nothing; store the Redis client and the database writer."""
        if sync_every <= 0:
            raise ValueError("sync_every must be a positive integer")
        self.redis_client = redis_client
        self.save_views = save_views or save_views_to_db
        self.sync_every = sync_every

    def increment_trial_views(self, trial_id: int) -> int:
        """Return the trial's view count after adding one view (synced to MySQL every 10)."""
        key = views_key(trial_id)
        count = int(self.redis_client.incr(key))
        if count % self.sync_every == 0:
            rows = self.save_views(trial_id, count)
            if rows != 1:
                raise ValueError(f"trial {trial_id} not found in the database")
            logger.info("Synced views to database (trial_id=%s, view_count=%s)", trial_id, count)
        return count

    def get_trial_views(self, trial_id: int) -> int:
        """Return the current view count stored in Redis (0 if the key does not exist)."""
        value = self.redis_client.get(views_key(trial_id))
        return int(value) if value is not None else 0
