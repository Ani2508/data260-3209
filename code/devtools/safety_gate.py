"""HW7 Part 6 - bash safety gate (pure Python, no model needed).

  SAFE_PREFIXES        module-level allow-list of read-only commands
  is_destructive(cmd)  independent deny-list check -> bool
  confirm_bash(cmd, auto_approve=False) -> {"allowed": bool, "reason": str}

Destructive commands are blocked unless explicit confirmation (auto_approve=True) is given,
even when they start with a safe prefix (e.g. "echo x > /etc/hosts", "find . -delete").
"""
from __future__ import annotations

import re
import shlex

SAFE_PREFIXES: tuple[str, ...] = (
    "ls", "pwd", "cat", "head", "tail", "wc", "grep", "find", "echo", "which", "file",
    "python3 -m py_compile", "python3 --version", "git status", "git diff", "git log",
)

# (category, pattern) - checked on every sub-command of a pipeline / chain
DENY_RULES: tuple[tuple[str, re.Pattern], ...] = (
    ("recursive deletion", re.compile(
        r"\brm\s+(?:-[a-z]*[rR][a-z]*|--recursive)\b|\bfind\b.*\s-(?:delete|exec\s+rm)\b"
        r"|\brmdir\s+(?:-p|--parents)\b")),
    ("privilege escalation", re.compile(r"(?:^|\s)(?:sudo|su|doas|pkexec)(?:\s|$)")),
    ("permission/ownership change", re.compile(r"(?:^|\s)(?:chmod|chown|chgrp|setfacl|chflags)\s")),
    ("raw-device write", re.compile(r"\bdd\b.*\bof=/dev/|>\s*/dev/(?!null\b)\w|"
                                    r"\b(?:shred|wipefs)\b.*\s/dev/")),
    ("filesystem creation", re.compile(r"\b(?:mkfs(?:\.\w+)?|mke2fs|newfs\w*|mkswap)\b|"
                                       r"\bdiskutil\s+(?:erase\w*|partitionDisk)\b")),
    ("redirection to root path", re.compile(r">>?\s*/(?!dev/null\b)|\btee\s+(?:-a\s+)?/")),
)


def _segments(command: str) -> list[str]:
    """Return the sub-commands of a chain/pipeline, including $(...) and `...` bodies."""
    inner = re.findall(r"\$\(([^)]*)\)|`([^`]*)`", command)
    parts = re.split(r"\|\||&&|[;|\n]", command)
    parts += [a or b for a, b in inner]
    return [p.strip() for p in parts if p.strip()]


def is_destructive(command: str) -> bool:
    """Return True if any part of the command matches the destructive deny-list."""
    return destructive_reason(command) is not None


def destructive_reason(command: str) -> str | None:
    """Return the deny-list category the command falls into, or None."""
    if not isinstance(command, str):
        raise ValueError("command must be a string")
    for seg in _segments(command):
        for category, pattern in DENY_RULES:
            if pattern.search(seg):
                return category
    return None


def _has_safe_prefix(segment: str) -> bool:
    """Return True if the segment starts with an allow-listed command (whole words)."""
    try:
        words = shlex.split(segment)
    except ValueError:
        return False
    for prefix in SAFE_PREFIXES:
        p = prefix.split()
        if words[:len(p)] == p:
            return True
    return False


def confirm_bash(command: str, auto_approve: bool = False) -> dict:
    """Return {"allowed", "reason"}; destructive commands need explicit confirmation."""
    if not isinstance(command, str) or not command.strip():
        return {"allowed": False, "reason": "empty command"}
    category = destructive_reason(command)
    if category:
        if auto_approve:
            return {"allowed": True, "reason": f"destructive ({category}) - explicitly confirmed"}
        return {"allowed": False, "reason": f"destructive ({category}) - needs confirmation"}
    if all(_has_safe_prefix(seg) for seg in _segments(command)):
        return {"allowed": True, "reason": "safe prefix"}
    if auto_approve:
        return {"allowed": True, "reason": "not on allow-list - explicitly confirmed"}
    return {"allowed": False, "reason": "not on allow-list - needs confirmation"}


def prefix_only_gate(command: str) -> dict:
    """Return the decision of a naive allow-list-only gate (used to expose false allows)."""
    ok = all(_has_safe_prefix(seg) for seg in _segments(command))
    return {"allowed": ok, "reason": "safe prefix" if ok else "not on allow-list"}
