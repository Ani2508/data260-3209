"""HW7 Part 6 - six file tools confined to one sandbox directory.

read_file(path, max_lines)          write_file(path, content)
edit_file(path, old, new) -> diff   glob_files(pattern)
search_in_files(query, file_pattern) bash(command, auto_approve) -> runs only if the gate allows
Every tool returns {"success": bool, "data" | "error"}; paths outside the sandbox are refused.
"""
from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

from .safety_gate import confirm_bash

MAX_DIFF_LINES = 20


def _ok(data) -> dict:
    return {"success": True, "data": data}


def _err(msg: str) -> dict:
    return {"success": False, "error": msg}


class FileTools:
    """The six tools bound to one sandbox root."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise ValueError(f"sandbox {self.root} does not exist")

    def _path(self, path: str) -> Path:
        """Return the absolute path inside the sandbox, or raise ValueError."""
        p = (self.root / path).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"path '{path}' is outside the sandbox")
        return p

    def _rel(self, p: Path) -> str:
        return str(p.relative_to(self.root))

    def read_file(self, path: str, max_lines: int | None = None) -> dict:
        """Return the file text (first max_lines lines if given)."""
        try:
            p = self._path(path)
            lines = p.read_text(encoding="utf-8").splitlines()
        except (ValueError, OSError) as exc:
            return _err(str(exc))
        if max_lines is not None and (not isinstance(max_lines, int) or max_lines < 1):
            return _err("max_lines must be a positive integer")
        shown = lines[:max_lines] if max_lines else lines
        return _ok({"path": self._rel(p), "content": "\n".join(shown),
                    "lines_returned": len(shown), "total_lines": len(lines),
                    "truncated": len(shown) < len(lines)})

    def write_file(self, path: str, content: str) -> dict:
        """Create or overwrite a file; return the bytes written."""
        try:
            p = self._path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            n = p.write_text(content, encoding="utf-8")
        except (ValueError, OSError) as exc:
            return _err(str(exc))
        return _ok({"path": self._rel(p), "bytes": n})

    def edit_file(self, path: str, old: str, new: str) -> dict:
        """Replace one exact occurrence of old with new; return a short unified diff."""
        try:
            p = self._path(path)
            before = p.read_text(encoding="utf-8")
        except (ValueError, OSError) as exc:
            return _err(str(exc))
        count = before.count(old) if old else 0
        if count != 1:
            return _err(f"old text must occur exactly once (found {count})")
        after = before.replace(old, new, 1)
        p.write_text(after, encoding="utf-8")
        diff = list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                         f"a/{self._rel(p)}", f"b/{self._rel(p)}",
                                         n=1, lineterm=""))
        if len(diff) > MAX_DIFF_LINES:
            diff = diff[:MAX_DIFF_LINES] + [f"... ({len(diff) - MAX_DIFF_LINES} more lines)"]
        return _ok({"path": self._rel(p), "diff": "\n".join(diff)})

    def glob_files(self, pattern: str = "**/*") -> dict:
        """Return sandbox files matching a glob pattern (sorted, relative paths)."""
        if ".." in pattern or pattern.startswith("/"):
            return _err("pattern must stay inside the sandbox")
        files = sorted(self._rel(p) for p in self.root.glob(pattern) if p.is_file())
        return _ok({"pattern": pattern, "files": files, "count": len(files)})

    def search_in_files(self, query: str, file_pattern: str = "**/*") -> dict:
        """Return lines containing query in files matching file_pattern."""
        if not query:
            return _err("query must not be empty")
        listed = self.glob_files(file_pattern)
        if not listed["success"]:
            return listed
        hits = []
        for rel in listed["data"]["files"]:
            try:
                text = (self.root / rel).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if query in line:
                    hits.append({"path": rel, "line": i, "text": line.strip()})
        return _ok({"query": query, "file_pattern": file_pattern, "matches": hits,
                    "files": sorted({h["path"] for h in hits})})

    def bash(self, command: str, auto_approve: bool = False, timeout: int = 10) -> dict:
        """Run a shell command in the sandbox only if confirm_bash allows it."""
        gate = confirm_bash(command, auto_approve)
        if not gate["allowed"]:
            return _err(f"blocked by safety gate: {gate['reason']}")
        try:
            res = subprocess.run(command, shell=True, cwd=self.root,
                                 capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return _err(f"timed out after {timeout}s")
        return _ok({"command": command, "gate": gate["reason"], "exit_code": res.returncode,
                    "stdout": res.stdout[-2000:], "stderr": res.stderr[-1000:]})
