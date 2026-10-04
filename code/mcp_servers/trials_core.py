"""Shared core for the s3209_rel domain tools (HW5 Parts 2B-5).

Every tool returns ONE envelope shape:  {"ok": bool, "data": ..., "error": str | None}
The data source is injected (a "store"), so the same tool code runs against
MySQL in the MCP server and against an in-memory fake in the offline tests.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

TRIAL_STATUSES = ("Recruiting", "Active - Not Recruiting", "Completed", "Terminated")
GROUP_BY_OPTIONS = ("status", "sponsor")
MAX_LIMIT = 25


# ---------------------------------------------------------------- envelope
def ok(data: Any) -> dict:
    return {"ok": True, "data": data, "error": None}


def fail(message: str) -> dict:
    return {"ok": False, "data": None, "error": message}


# ---------------------------------------------------------------- input schemas
TOOL_SCHEMAS: dict[str, dict] = {
    "search_trials": {
        "description": "Search clinical trials by words in the title or sponsor name, "
                       "optionally filtered by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 2, "description": "text to search for"},
                "status": {"type": "string", "enum": list(TRIAL_STATUSES)},
                "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "default": 10},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    "get_trial": {
        "description": "Get the full record of one trial by its numeric id.",
        "input_schema": {
            "type": "object",
            "properties": {"trial_id": {"type": "integer", "minimum": 1}},
            "required": ["trial_id"],
            "additionalProperties": False,
        },
    },
    "trial_stats": {
        "description": "Aggregate: number of trials and total open enrollment slots, "
                       "grouped by status or by sponsor.",
        "input_schema": {
            "type": "object",
            "properties": {"group_by": {"type": "string", "enum": list(GROUP_BY_OPTIONS),
                                        "default": "status"}},
            "required": [],
            "additionalProperties": False,
        },
    },
}


# ---------------------------------------------------------------- MySQL store
class SQLTrialStore:
    """Reads the s3209_rel tables (sponsors, trials) with plain SQL."""

    def __init__(self, url: str | None = None):
        from sqlalchemy import create_engine
        self.engine = create_engine(url or _db_url(), pool_pre_ping=True)

    def _rows(self, sql: str, **params) -> list[dict]:
        from sqlalchemy import text
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(text(sql), params)]

    def search(self, query: str, status: str | None, limit: int) -> list[dict]:
        sql = ("SELECT t.id, t.trial_title, t.nct_id, t.status, t.enrollment_slots, "
               "s.name AS sponsor FROM trials t JOIN sponsors s ON s.id = t.sponsor_id "
               "WHERE (t.trial_title LIKE :q OR s.name LIKE :q)")
        if status:
            sql += " AND t.status = :status"
        sql += " ORDER BY t.id LIMIT :limit"
        return self._rows(sql, q=f"%{query}%", status=status, limit=limit)

    def get(self, trial_id: int) -> dict | None:
        rows = self._rows(
            "SELECT t.id, t.trial_title, t.nct_id, t.status, t.enrollment_slots, "
            "t.sponsor_id, s.name AS sponsor, s.country AS sponsor_country, "
            "t.created_at, t.updated_at FROM trials t JOIN sponsors s ON s.id = t.sponsor_id "
            "WHERE t.id = :id", id=trial_id)
        if not rows:
            return None
        row = rows[0]
        for key in ("created_at", "updated_at"):
            row[key] = str(row[key])
        return row

    def stats(self, group_by: str) -> list[dict]:
        key = "t.status" if group_by == "status" else "s.name"
        rows = self._rows(
            f"SELECT {key} AS grp, COUNT(*) AS trials, "
            "COALESCE(SUM(t.enrollment_slots), 0) AS open_slots "
            "FROM trials t JOIN sponsors s ON s.id = t.sponsor_id "
            f"GROUP BY {key} ORDER BY trials DESC, grp")
        # MySQL returns SUM() as Decimal -> make both counts plain ints for JSON
        return [{"grp": r["grp"], "trials": int(r["trials"]), "open_slots": int(r["open_slots"])}
                for r in rows]


def _db_url() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass
    from sqlalchemy.engine import URL
    return URL.create("mysql+pymysql", username=os.getenv("DB_USER", "root"),
                      password=os.getenv("DB_PASSWORD", ""),
                      host=os.getenv("DB_HOST", "localhost"),
                      port=int(os.getenv("DB_PORT", "3306")),
                      database=os.getenv("DB_NAME", "s3209_rel"))


# ---------------------------------------------------------------- the 3 tools
def _bad_keys(inputs: dict, tool: str) -> str | None:
    allowed = set(TOOL_SCHEMAS[tool]["input_schema"]["properties"])
    extra = sorted(set(inputs) - allowed)
    return f"unknown field(s): {', '.join(extra)}" if extra else None


def search_trials(store, inputs: dict) -> dict:
    if (msg := _bad_keys(inputs, "search_trials")):
        return fail(msg)
    query = inputs.get("query")
    if not isinstance(query, str) or len(query.strip()) < 2:
        return fail("query is required and must be a string of at least 2 characters")
    status = inputs.get("status")
    if status is not None and status not in TRIAL_STATUSES:
        return fail(f"status must be one of {list(TRIAL_STATUSES)}")
    limit = inputs.get("limit", 10)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
        return fail(f"limit must be an integer between 1 and {MAX_LIMIT}")
    rows = store.search(query.strip(), status, limit)
    return ok({"count": len(rows), "results": rows})


def get_trial(store, inputs: dict) -> dict:
    if (msg := _bad_keys(inputs, "get_trial")):
        return fail(msg)
    trial_id = inputs.get("trial_id")
    if isinstance(trial_id, bool) or not isinstance(trial_id, int) or trial_id < 1:
        return fail("trial_id is required and must be a positive integer")
    row = store.get(trial_id)
    if row is None:
        return fail(f"trial {trial_id} not found")
    return ok(row)


def trial_stats(store, inputs: dict) -> dict:
    if (msg := _bad_keys(inputs, "trial_stats")):
        return fail(msg)
    group_by = inputs.get("group_by", "status")
    if group_by not in GROUP_BY_OPTIONS:
        return fail(f"group_by must be one of {list(GROUP_BY_OPTIONS)}")
    groups = store.stats(group_by)
    return ok({"group_by": group_by, "groups": groups,
               "total_trials": sum(g["trials"] for g in groups)})


TOOLS: dict[str, Callable[[Any, dict], dict]] = {
    "search_trials": search_trials,
    "get_trial": get_trial,
    "trial_stats": trial_stats,
}
