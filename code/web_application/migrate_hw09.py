"""HW9 migration: add trials.view_count (INT NOT NULL DEFAULT 0) for the Redis view counter.

Idempotent and non-destructive: existing rows keep their data and start at 0.
Run:  python migrate_hw09.py
"""
from __future__ import annotations

from sqlalchemy import inspect, text

from database import engine


def migrate_schema() -> list[str]:
    """Return the ALTER statements applied to add trials.view_count."""
    cols = {c["name"] for c in inspect(engine).get_columns("trials")}
    if "view_count" in cols:
        return []
    sql = "ALTER TABLE trials ADD COLUMN view_count INT NOT NULL DEFAULT 0 AFTER status"
    with engine.begin() as conn:
        conn.execute(text(sql))
    return [sql]


if __name__ == "__main__":
    print("Run by: Ani Taraiya (s3209)")
    for stmt in migrate_schema() or ["(schema already up to date)"]:
        print("schema:", stmt)
    with engine.connect() as conn:
        for row in conn.execute(text("SHOW COLUMNS FROM trials")):
            print(f"  {row[0]:<18} {row[1]:<14} null={row[2]:<4} default={row[4]}")
