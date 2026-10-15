"""File-based memory: AGENT.md + MEMORY.md (HW6 Part 4).

MEMORY.md format
    <!-- last_consolidated: 2026-10-15T09:00:00 -->
    - [YYYY-MM-DD] key: value {src=protocol|chat|team}
Lines inside <!-- --> are comments and are not counted.
"""
import json
import re
import sys
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = ROOT / "AGENT.md"
MEMORY_PATH = ROOT / "MEMORY.md"

MAX_LINES = 40
MAX_AGE = timedelta(hours=24)
STAMP_RE = re.compile(r"<!--\s*last_consolidated:\s*([0-9T:\-]+)\s*-->")
FACT_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2})\] ([a-z0-9_.]+):\s*(.+?)(?:\s*\{src=(\w+)\})?\s*$")
SOURCE_RANK = {"protocol": 3, "team": 2, "chat": 1}


# ------------------------------------------------------------------ load + prompt
def load_memory_files(agent_path: Path = AGENT_PATH, memory_path: Path = MEMORY_PATH) -> dict:
    """Read both Markdown files (missing file -> empty string)."""
    read = lambda p: p.read_text(encoding="utf-8") if p.exists() else ""
    return {"agent": read(agent_path), "memory": read(memory_path)}


def build_system_prompt(files: dict, base: str = "") -> str:
    """Add AGENT.md (instructions) and MEMORY.md (durable facts) to the system prompt."""
    parts = [base.strip()] if base.strip() else []
    if files["agent"].strip():
        parts.append("## Project and agent instructions (AGENT.md)\n" + files["agent"].strip())
    if files["memory"].strip():
        facts = "\n".join(content_lines(files["memory"]))
        parts.append("## Durable facts from earlier conversations (MEMORY.md)\n" + facts)
    return "\n\n".join(parts)


# ------------------------------------------------------------------ consolidation checks
def content_lines(text: str) -> list:
    """Non-empty, non-comment lines."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return [ln for ln in text.splitlines() if ln.strip()]


def read_last_consolidated(text: str):
    m = STAMP_RE.search(text)
    if not m:
        return None
    try:
        return datetime.fromisoformat(m.group(1))
    except ValueError:
        return None


def needs_consolidation(text: str, now: datetime | None = None) -> tuple:
    """True when > 40 content lines, or the recorded consolidation time is > 24 h old (or missing)."""
    now = now or datetime.now()
    n = len(content_lines(text))
    last = read_last_consolidated(text)
    reasons = []
    if n > MAX_LINES:
        reasons.append(f"{n} content lines > {MAX_LINES}")
    if last is None:
        reasons.append("no last_consolidated timestamp")
    elif now - last > MAX_AGE:
        reasons.append(f"last consolidated {now - last} ago (> 24h)")
    return bool(reasons), reasons


# ------------------------------------------------------------------ consolidation
def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def parse_facts(text: str) -> list:
    facts = []
    for ln in content_lines(text):
        m = FACT_RE.match(ln.strip())
        if m:
            facts.append({"date": m.group(1), "key": m.group(2), "value": m.group(3).strip(),
                          "src": m.group(4) or "chat"})
    return facts


def consolidate(text: str, now: datetime | None = None) -> tuple:
    """Merge duplicates, resolve contradictions explicitly, flag suspect resolutions.

    Rule for a contradiction (same key, different values): higher source rank wins
    (protocol > team > chat); on a tie the newest date wins. Every discarded value is
    written to the 'Resolved contradictions' section - nothing is deleted silently.
    A resolution is flagged SUSPECT when the discarded value was confirmed more times
    than the kept one (the rule may have picked the wrong value).
    """
    now = now or datetime.now()
    facts = parse_facts(text)
    groups = OrderedDict()
    for f in facts:
        groups.setdefault(f["key"], []).append(f)

    kept, resolved, suspects = [], [], []
    duplicates_merged = 0
    for key, items in groups.items():
        variants = OrderedDict()                       # normalized value -> merged entry
        for f in items:
            nv = _norm(f["value"])
            if nv in variants:
                v = variants[nv]
                v["count"] += 1
                duplicates_merged += 1
                v["date"] = max(v["date"], f["date"])
                if SOURCE_RANK[f["src"]] > SOURCE_RANK[v["src"]]:
                    v["src"] = f["src"]
            else:
                variants[nv] = dict(f, count=1)
        vals = list(variants.values())
        winner = max(vals, key=lambda v: (SOURCE_RANK[v["src"]], v["date"]))
        kept.append(winner)
        for loser in vals:
            if loser is winner:
                continue
            rule = "higher source" if SOURCE_RANK[loser["src"]] != SOURCE_RANK[winner["src"]] else "newer date"
            entry = {"key": key, "kept": winner["value"], "kept_date": winner["date"],
                     "kept_src": winner["src"], "kept_count": winner["count"],
                     "dropped": loser["value"], "dropped_date": loser["date"],
                     "dropped_src": loser["src"], "dropped_count": loser["count"], "rule": rule}
            resolved.append(entry)
            if loser["count"] > winner["count"]:
                suspects.append(entry)

    lines = ["# MEMORY.md - durable facts (s3209)",
             f"<!-- last_consolidated: {now.isoformat(timespec='seconds')} -->",
             "<!-- format: - [YYYY-MM-DD] key: value {src=protocol|team|chat} -->", "",
             "## Facts"]
    for v in kept:
        note = f" <!-- merged x{v['count']} -->" if v["count"] > 1 else ""
        lines.append(f"- [{v['date']}] {v['key']}: {v['value']} {{src={v['src']}}}{note}")
    if resolved:
        lines += ["", "## Resolved contradictions"]
        for r in resolved:
            flag = " SUSPECT: dropped value had more confirmations" if r in suspects else ""
            lines.append(f"- {r['key']}: kept \"{r['kept']}\" ({r['kept_src']}, {r['kept_date']}) over "
                         f"\"{r['dropped']}\" ({r['dropped_src']}, {r['dropped_date']}) - {r['rule']}{flag}")
    new_text = "\n".join(lines) + "\n"
    report = {"lines_before": len(content_lines(text)), "lines_after": len(content_lines(new_text)),
              "facts_before": len(facts), "facts_after": len(kept),
              "duplicates_merged": duplicates_merged, "contradictions_resolved": len(resolved),
              "suspect_resolutions": suspects, "resolutions": resolved}
    return new_text, report


# ------------------------------------------------------------------ /dream helper
def append_facts(text: str, new_facts: list, today: str | None = None) -> tuple:
    """Append {key, value} facts not already present (same key + same value)."""
    today = today or datetime.now().strftime("%Y-%m-%d")
    have = {(f["key"], _norm(f["value"])) for f in parse_facts(text)}
    added = []
    for f in new_facts:
        key = re.sub(r"[^a-z0-9_.]+", "_", str(f.get("key", "")).lower()).strip("_")
        val = str(f.get("value", "")).strip().replace("\n", " ")
        if key and val and (key, _norm(val)) not in have:
            added.append(f"- [{today}] {key}: {val} {{src=chat}}")
            have.add((key, _norm(val)))
    if added:
        text = text.rstrip("\n") + "\n" + "\n".join(added) + "\n"
    return text, added


if __name__ == "__main__":       # quick check: python3 file_memory.py MEMORY.md
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else MEMORY_PATH
    t = path.read_text()
    print(json.dumps({"content_lines": len(content_lines(t)),
                      "last_consolidated": str(read_last_consolidated(t)),
                      "needs_consolidation": needs_consolidation(t)}, indent=2))
