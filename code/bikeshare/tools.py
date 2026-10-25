"""HW7 Part 4 - MRKL tools for the bike-share advisor (pure functions + JSON schemas).

Every tool returns the common shape {"success", "data", "error", "source", "ts"}.

  csv_sql           {"sql"}                    -> {"rows", "row_count", "source": "uploaded.csv"}
  policy_retriever  {"url", "query", "k"?}     -> {"passages": [{"text", "source", "score"}]}
  calculator        {"expression", "units"?}   -> {"value", "units"?}

Part 5 defenses are switchable (DEFENSES) so the same tools can be attacked before/after:
  prompt: retrieved text is wrapped and labelled as untrusted data
  tool:   csv_sql accepts exactly one read-only SELECT (enforced in code, not by the prompt)
"""
from __future__ import annotations

import ast
import csv
import hashlib
import html
import json
import operator
import re
import sqlite3
import urllib.request
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

DEFENSES = {"prompt": True, "tool": True}
MAX_ROWS = 200                 # csv_sql never returns more rows than this
CALC_RE = re.compile(r"^[0-9+\-*/().\s]+$")

CSV_SQL_SCHEMA = {
    "name": "csv_sql",
    "description": "Run ONE read-only SQL SELECT over the uploaded trips (SQLite table `trips`).",
    "input_schema": {"type": "object", "properties": {"sql": {"type": "string"}},
                     "required": ["sql"], "additionalProperties": False},
    "output_schema": {"type": "object", "properties": {
        "rows": {"type": "array", "items": {"type": "object"}},
        "row_count": {"type": "number"}, "source": {"const": "uploaded.csv"}}},
}
POLICY_RETRIEVER_SCHEMA = {
    "name": "policy_retriever",
    "description": "Fetch the pricing page URL and return short quotable passages for a query.",
    "input_schema": {"type": "object", "properties": {
        "url": {"type": "string"}, "query": {"type": "string"},
        "k": {"type": "integer", "minimum": 3, "maximum": 10, "default": 5}},
        "required": ["url", "query"], "additionalProperties": False},
    "output_schema": {"type": "object", "properties": {"passages": {"type": "array", "items": {
        "type": "object", "properties": {"text": {"type": "string"}, "source": {"type": "string"},
                                         "score": {"type": "number"}}}}}},
}
CALCULATOR_SCHEMA = {
    "name": "calculator",
    "description": "Safe arithmetic on numbers with + - * / and parentheses (no eval).",
    "input_schema": {"type": "object", "properties": {
        "expression": {"type": "string", "pattern": r"^[0-9+\-*/().\s]+$"},
        "units": {"type": "string"}}, "required": ["expression"], "additionalProperties": False},
    "output_schema": {"type": "object", "properties": {"value": {"type": "number"},
                                                       "units": {"type": "string"}}},
}
SCHEMAS = [CSV_SQL_SCHEMA, POLICY_RETRIEVER_SCHEMA, CALCULATOR_SCHEMA]


def _now() -> str:
    """Return the current UTC time as an ISO string."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def envelope(success: bool, data=None, error: str | None = None, source: str | None = None) -> dict:
    """Return the common tool result shape."""
    out = {"success": success, "ts": _now()}
    if success:
        out["data"] = data
    else:
        out["error"] = error
    if source:
        out["source"] = source
    return out


# ---------------------------------------------------------------- csv_sql
TRIP_COLUMNS = """ride_id, rider_id, rideable_type, started_at, ended_at, start_station_name,
end_station_name, member_casual, duration_min (derived), week_start (derived, Monday),
month (derived, YYYY-MM)"""


class TripDB:
    """In-memory SQLite copy of the uploaded CSV (the original file is never modified)."""

    def __init__(self, csv_path: str | Path):
        self.path = Path(csv_path)
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.notes: list[str] = []
        self._load()

    def _load(self) -> None:
        with open(self.path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("uploaded CSV has no rows")
        cols = list(rows[0])
        self.conn.execute(f"CREATE TABLE trips ({', '.join(c + ' TEXT' for c in cols)}, "
                          "duration_min REAL, week_start TEXT, month TEXT)")
        bad = 0
        for r in rows:
            try:
                s = datetime.fromisoformat(r["started_at"])
                e = datetime.fromisoformat(r["ended_at"])
                dur = round((e - s).total_seconds() / 60, 2)
                week = (s.date().toordinal() - s.weekday())
                week_start = datetime.fromordinal(week).date().isoformat()
                month = s.strftime("%Y-%m")
            except (KeyError, ValueError):
                dur, week_start, month = None, None, None
                bad += 1
            self.conn.execute(f"INSERT INTO trips VALUES ({', '.join('?' * (len(cols) + 3))})",
                              [r[c] for c in cols] + [dur, week_start, month])
        self.conn.commit()
        if bad:
            self.notes.append(f"{bad} rows have unreadable start/end times (duration NULL)")


_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}


def _readonly_authorizer(action, *_):
    """SQLite authorizer: allow only reading (any write, DDL, ATTACH, PRAGMA is denied)."""
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def _single_select(sql: str) -> str | None:
    """Return a problem if sql is not exactly one SELECT statement, else None."""
    body = sql.strip().rstrip(";").strip()
    if not body:
        return "empty SQL"
    if ";" in body:
        return "only one statement is allowed"
    if not re.match(r"(?is)^(select|with)\b", body):
        return "only read-only SELECT queries are allowed"
    return None


def csv_sql(db: TripDB, sql: str) -> dict:
    """Run SQL over the uploaded trips; with the tool defense on, only one read-only SELECT."""
    try:
        if DEFENSES["tool"]:
            problem = _single_select(sql)
            if problem:
                return envelope(False, error=f"rejected by csv_sql contract: {problem}",
                                source="uploaded.csv")
            db.conn.set_authorizer(_readonly_authorizer)
            try:
                cur = db.conn.execute(sql.strip().rstrip(";"))
            finally:
                db.conn.set_authorizer(None)
        else:                                   # undefended: runs whatever it is given
            cur = db.conn.cursor()
            stmts = [s for s in sql.split(";") if s.strip()]
            for s in stmts:
                cur.execute(s)
            db.conn.commit()
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = [dict(zip(cols, r, strict=False)) for r in cur.fetchmany(MAX_ROWS + 1)]
        truncated = len(rows) > MAX_ROWS
        data = {"rows": rows[:MAX_ROWS], "row_count": min(len(rows), MAX_ROWS),
                "source": "uploaded.csv"}
        if truncated:
            data["truncated"] = f"only the first {MAX_ROWS} rows are returned"
        return envelope(True, data, source="uploaded.csv")
    except sqlite3.Error as exc:
        return envelope(False, error=f"SQL error: {exc}", source="uploaded.csv")


# ---------------------------------------------------------------- policy_retriever
class _TextExtractor(HTMLParser):
    """Collect visible text blocks from HTML (scripts/styles dropped)."""
    BLOCK = {"p", "li", "td", "th", "h1", "h2", "h3", "h4", "div", "section", "br", "tr", "span"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_text(raw: str) -> str:
    """Return the visible text of an HTML page, one block per line."""
    p = _TextExtractor()
    p.feed(raw)
    lines = (" ".join(html.unescape(x).split()) for x in "".join(p.parts).split("\n"))
    return "\n".join(x for x in lines if x)


class PageCache:
    """Fetches each URL once per run and records the snapshot evidence (text, time, SHA-256)."""

    def __init__(self):
        self.pages: dict[str, dict] = {}
        self.passage_ids: dict[str, str] = {}      # passage text -> stable id P1, P2, ...

    def pid(self, text: str) -> str:
        """Return the run-wide id of a passage (same text -> same id)."""
        if text not in self.passage_ids:
            self.passage_ids[text] = f"P{len(self.passage_ids) + 1}"
        return self.passage_ids[text]

    def get(self, url: str) -> dict:
        if url not in self.pages:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (s3209 HW7)"})
            with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310 (user-given URL)
                raw = resp.read().decode("utf-8", errors="replace")
            text = html_to_text(raw) if "<" in raw[:2000] else raw
            self.pages[url] = {"url": url, "accessed_at": _now(), "text": text,
                               "sha256": hashlib.sha256(text.encode()).hexdigest()}
        return self.pages[url]


def _passages(text: str) -> list[str]:
    """Return short passages: each line and windows of 2-6 neighbouring lines (<= 300 chars).

    Wide windows keep a flattened table row (label + its cells) together."""
    lines = [x for x in text.split("\n") if 2 < len(x) < 400]
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        for width in range(2, 7):
            window = lines[i:i + width]
            if len(window) == width and sum(len(w) for w in window) < 300:
                out.append(" | ".join(window))
    return out


def _score(passage: str, query: str) -> float:
    """Return a keyword-overlap score; prices and minutes get a small boost."""
    stems = {w[:5] for w in re.findall(r"[a-z0-9]+", passage.lower())}
    q = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
    if not q:
        return 0.0
    overlap = sum(1 for w in q if w[:5] in stems) / len(q)      # 5-letter stem match
    boost = 0.2 * bool(re.search(r"\$\s?\d", passage)) + 0.1 * bool(re.search(r"\bmin", passage))
    return round(overlap + boost - 0.001 * len(passage) / 10, 3)


def policy_retriever(cache: PageCache, url: str, query: str, k: int = 5) -> dict:
    """Return the k best short passages from the pricing page for the query."""
    try:
        if not re.match(r"^https?://", url):
            return envelope(False, error="url must start with http:// or https://")
        k = max(3, min(int(k or 5), 10))      # short passages: always return at least 3
        page = cache.get(url)
        ranked = sorted(_passages(page["text"]), key=lambda p: _score(p, query), reverse=True)
        top = []
        for p in ranked:          # skip passages that overlap one already chosen
            if any(p in t["text"] or t["text"] in p for t in top):
                continue
            top.append({"id": cache.pid(p[:300]), "text": p[:300], "source": url,
                        "score": _score(p, query)})
            if len(top) == k:
                break
        if DEFENSES["prompt"]:   # label retrieved text as untrusted data for the model
            for t in top:
                t["text"] = f"<untrusted_page_text>{t['text']}</untrusted_page_text>"
        return envelope(True, {"passages": top, "accessed_at": page["accessed_at"]}, source=url)
    except Exception as exc:  # network, decoding, bad URL -> structured error
        return envelope(False, error=f"{type(exc).__name__}: {exc}", source=url)


# ---------------------------------------------------------------- calculator
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str, units: str | None = None) -> dict:
    """Return the value of a whitelisted arithmetic expression (parsed, never eval'd)."""
    if not isinstance(expression, str) or not CALC_RE.match(expression):
        return envelope(False, error="expression may only contain digits, + - * / ( ) . and spaces")
    try:
        value = round(float(_eval(ast.parse(expression, mode="eval"))), 4)
    except ZeroDivisionError:
        return envelope(False, error="division by zero")
    except (ValueError, SyntaxError) as exc:
        return envelope(False, error=f"bad expression: {exc}")
    data = {"value": value}
    if units:
        data["units"] = units
    return envelope(True, data)


def to_json(result: dict) -> str:
    """Return a tool result as compact JSON text for the agent."""
    return json.dumps(result, default=str)
