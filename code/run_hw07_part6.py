"""HW7 Part 6 - one combined run: (a) glob -> search -> read integration test driven by one
instruction to the agent, (b) 10-command safety-gate test, plus checks of the file tools.

  python code/run_hw07_part6.py

Everything happens inside a fresh temporary sandbox directory; raw results go to
reports/hw07/raw/part6_results.json.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from devtools.file_tools import FileTools  # noqa: E402
from devtools.safety_gate import (  # noqa: E402
    SAFE_PREFIXES,
    confirm_bash,
    destructive_reason,
    is_destructive,
    prefix_only_gate,
)

RAW = ROOT / "reports/hw07/raw"
FILES = {
    "app.py": 'DEBUG = True\n\n\ndef main():\n    print("trial registry app")\n',
    "utils.py": 'def slugify(text):\n    return text.lower().replace(" ", "-")\n',
    "models.py": 'class Trial:\n    def __init__(self, title):\n        self.title = title\n',
}
INSTRUCTION = "Find the Python file in the sandbox that contains DEBUG and show me its contents."
GATE_CASES = [  # (command, expected allowed)
    ("ls -la", True), ("cat app.py", True), ("grep -rn DEBUG .", True),
    ("python3 -m py_compile app.py", True), ("git status", True),
    ("rm -rf build", False), ("sudo rm /tmp/cache.db", False), ("chmod -R 777 .", False),
    ("dd if=/dev/zero of=/dev/disk2 bs=1m", False), ("echo pwned > /etc/hosts", False),
]


def file_agent(tools: FileTools, model=None):
    """Return a LangChain ReAct agent that can use glob_files, search_in_files and read_file."""
    from langchain.agents import create_agent
    from langchain_core.tools import StructuredTool
    if model is None:
        from langchain_ollama import ChatOllama
        model = ChatOllama(model="qwen3:8b", temperature=0, seed=3209, reasoning=False)

    def glob_files(pattern: str) -> str:
        """List sandbox files matching a glob pattern such as *.py."""
        return json.dumps(tools.glob_files(pattern))

    def search_in_files(query: str, file_pattern: str = "*.py") -> str:
        """Find lines containing query in files matching file_pattern."""
        return json.dumps(tools.search_in_files(query, file_pattern))

    def read_file(path: str, max_lines: int | None = None) -> str:
        """Read a sandbox file (optionally only the first max_lines lines)."""
        return json.dumps(tools.read_file(path, max_lines))

    system = ("You work inside a sandbox folder with file tools. To find something, always "
              "1) call glob_files to list candidate files, 2) call search_in_files on them, "
              "3) call read_file on the matching file. Then answer with the file name and its "
              "full contents.")
    fns = [StructuredTool.from_function(f) for f in (glob_files, search_in_files, read_file)]
    return create_agent(model, fns, system_prompt=system)


def run_integration(tools: FileTools, model=None) -> dict:
    """Give the one instruction to the agent; return the tool sequence and final answer."""
    agent = file_agent(tools, model)
    t0 = time.perf_counter()
    out = agent.invoke({"messages": [{"role": "user", "content": INSTRUCTION}]},
                       config={"recursion_limit": 20})
    calls, final = [], ""
    for m in out["messages"]:
        for c in getattr(m, "tool_calls", None) or []:
            calls.append({"tool": c["name"], "args": c["args"]})
        if m.type == "ai" and not getattr(m, "tool_calls", None):
            final = m.content
    order = [c["tool"] for c in calls]
    read_paths = [c["args"].get("path") for c in calls if c["tool"] == "read_file"]
    needed = ("glob_files", "search_in_files", "read_file")
    seq_ok = (all(t in order for t in needed)
              and order.index(needed[0]) < order.index(needed[1]) < order.index(needed[2]))
    return {"instruction": INSTRUCTION, "calls": calls, "final": final,
            "glob_search_read_order": seq_ok,
            "found_debug_file": "app.py" in read_paths and "DEBUG = True" in final,
            "ms": round((time.perf_counter() - t0) * 1000)}


def run_gate() -> dict:
    """Return the 10-command results for the naive prefix gate and the final gate."""
    rows = []
    for cmd, expect in GATE_CASES:
        naive = prefix_only_gate(cmd)
        final = confirm_bash(cmd)
        rows.append({"command": cmd, "expected_allowed": expect,
                     "is_destructive": is_destructive(cmd),
                     "category": destructive_reason(cmd),
                     "prefix_only_allowed": naive["allowed"],
                     "false_allow_prefix_only": naive["allowed"] and not expect,
                     "allowed": final["allowed"], "reason": final["reason"],
                     "correct": final["allowed"] == expect})
    confirmed = confirm_bash("rm -rf build", auto_approve=True)
    return {"rows": rows, "confirmed_example": {"command": "rm -rf build", **confirmed}}


def main() -> None:
    sandbox = Path(tempfile.mkdtemp(prefix="data260_hw7_sandbox_"))
    tools = FileTools(sandbox)
    print("\n================ HW7 Part 6: file tools + safety gate ================")
    print(f"Run by: Ani Taraiya (s3209)   sandbox: {sandbox}")
    print(f"  SAFE_PREFIXES = {', '.join(SAFE_PREFIXES)}")
    try:
        for name, text in FILES.items():
            tools.write_file(name, text)
        print(f"  created: {', '.join(FILES)}")

        print(f"\n(a) Integration test - instruction: \"{INSTRUCTION}\"")
        integ = run_integration(tools)
        for i, c in enumerate(integ["calls"], 1):
            print(f"  {i}. {c['tool']}({json.dumps(c['args'])})")
        print("  agent answer:")
        for line in integ["final"].strip().splitlines():
            print(f"    | {line}")
        order_ok = "PASS" if integ["glob_search_read_order"] else "FAIL"
        found_ok = "PASS" if integ["found_debug_file"] else "FAIL"
        print(f"  glob -> search -> read order: {order_ok} | DEBUG file shown: {found_ok}")

        print("\n(b) Safety-gate test (expected: 5 allowed, 5 blocked)")
        gate = run_gate()
        print(f"  {'command':<38} {'expect':<7} {'prefix-only':<12} {'final gate':<10} reason")
        for r in gate["rows"]:
            exp = "allow" if r["expected_allowed"] else "block"
            naive = "ALLOW" if r["prefix_only_allowed"] else "block"
            if r["false_allow_prefix_only"]:
                naive += "*"
            fin = "ALLOW" if r["allowed"] else "BLOCK"
            print(f"  {r['command']:<38} {exp:<7} {naive:<12} {fin:<10} {r['reason']}")
        fa = [r["command"] for r in gate["rows"] if r["false_allow_prefix_only"]]
        print(f"  * false allow with the prefix-only gate: {fa or 'none'} -> fixed by "
              "is_destructive() running before the allow-list")
        ok = sum(r["correct"] for r in gate["rows"])
        print(f"  final gate correct: {ok}/10 | false allows left: "
              f"{sum(r['allowed'] and not r['expected_allowed'] for r in gate['rows'])}")
        c = gate["confirmed_example"]
        print(f"  with explicit confirmation: '{c['command']}' -> allowed={c['allowed']} "
              f"({c['reason']})")

        print("\n(c) File-tool checks")
        r = tools.read_file("app.py", max_lines=1)["data"]
        print(f"  read_file(app.py, max_lines=1) -> {r['content']!r} "
              f"({r['lines_returned']}/{r['total_lines']} lines)")
        d = tools.edit_file("app.py", "DEBUG = True", "DEBUG = False")["data"]["diff"]
        print("  edit_file diff:  " + "\n                   ".join(d.splitlines()))
        s = tools.search_in_files("def ", file_pattern="u*.py")["data"]
        print(f"  search_in_files('def ', file_pattern='u*.py') -> {s['files']}")
        print(f"  bash('ls') -> {tools.bash('ls')['data']['stdout'].split()}")
        print(f"  bash('rm -rf .') -> {tools.bash('rm -rf .')['error']}")
        print(f"  read_file('../outside.txt') -> {tools.read_file('../outside.txt')['error']}")
        RAW.mkdir(parents=True, exist_ok=True)
        (RAW / "part6_results.json").write_text(json.dumps(
            {"sandbox": str(sandbox), "integration": integ, "gate": gate}, indent=2))
        print("  raw: reports/hw07/raw/part6_results.json")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
        print(f"  sandbox removed: {sandbox}")


if __name__ == "__main__":
    main()
