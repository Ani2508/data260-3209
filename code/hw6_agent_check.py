"""HW6 Part 4.4 - generate one function with AGENT.md as the system prompt,
then verify the result against the AGENT.md rules (static checks + offline tests).

Run: python3 code/hw6_agent_check.py
Out: reports/hw06/raw/generated_function.py, reports/hw06/raw/agent_check.json
"""
import ast
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from model_client import ModelClient  # noqa: E402

RAW = ROOT / "reports" / "hw06" / "raw"
MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
STDLIB = set(getattr(sys, "stdlib_module_names", ())) or {"datetime", "re", "math", "typing"}

TASK = (
    "Write a Python function days_until_irb_review(due_date, today) that takes two ISO date strings "
    "(YYYY-MM-DD) and returns the number of days from today until the IRB continuing review is due "
    "(negative if overdue). Follow every rule in AGENT.md. After the function, add the tests that "
    "AGENT.md requires. Return only Python code in one ```python block."
)


def extract_code(text: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text, flags=re.S)
    return (m.group(1) if m else text).strip() + "\n"


def run_checks(code: str) -> list:
    tree = ast.parse(code)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    main = next((f for f in funcs if f.name == "days_until_irb_review"), None)
    checks = []

    def add(rule, ok, detail):
        checks.append({"agent_md_rule": rule, "pass": bool(ok), "detail": detail})

    add("snake_case function names", funcs and all(re.fullmatch(r"[a-z_][a-z0-9_]*", f.name) for f in funcs),
        [f.name for f in funcs])
    if main is None:
        add("function exists", False, "days_until_irb_review not found")
        return checks
    args = main.args.args
    add("type hints on every parameter and the return value",
        all(a.annotation is not None for a in args) and main.returns is not None,
        {a.arg: ast.unparse(a.annotation) if a.annotation else None for a in args}
        | {"return": ast.unparse(main.returns) if main.returns else None})
    doc = ast.get_docstring(main)
    add("one-line docstring that states what it returns", bool(doc) and "return" in doc.lower(), doc)
    prints = [n for n in ast.walk(main) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"]
    add("no print() in library code", not prints, f"{len(prints)} print call(s)")
    raises = [n for n in ast.walk(main) if isinstance(n, ast.Raise)]
    raises_value = any("ValueError" in ast.unparse(r) for r in raises)
    add("validates input and raises ValueError", raises_value, f"{len(raises)} raise statement(s)")
    imports = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imports |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            imports.add(n.module.split(".")[0])
    add("standard library only / no direct model API", imports <= STDLIB and not imports & {"ollama", "requests"},
        sorted(imports))
    asserts = [n for n in ast.walk(tree) if isinstance(n, ast.Assert)]
    add("at least three assert tests", len(asserts) >= 3, f"{len(asserts)} assert(s)")
    secrets = re.findall(r"(?i)(password|api_key|secret)\s*=", code)
    add("no hard-coded secrets", not secrets, secrets)
    return checks


def run_tests(path: Path) -> dict:
    """Run the generated file offline (its asserts are the tests) + 3 independent checks."""
    extra = (
        "\nassert days_until_irb_review('2027-03-14', '2027-03-01') == 13\n"
        "assert days_until_irb_review('2027-03-01', '2027-03-14') == -13\n"
        "try:\n    days_until_irb_review('14/03/2027', '2027-03-01')\n    raise SystemExit('no ValueError')\n"
        "except ValueError:\n    pass\nprint('independent checks passed')\n"
    )
    own = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=30)
    tmp = path.with_name("_agent_check_tmp.py")
    tmp.write_text(path.read_text() + extra)
    ind = subprocess.run([sys.executable, str(tmp)], capture_output=True, text=True, timeout=30)
    tmp.unlink()
    return {"own_tests_exit_code": own.returncode, "own_tests_stderr": own.stderr[-300:],
            "independent_tests_exit_code": ind.returncode,
            "independent_tests_output": (ind.stdout + ind.stderr)[-300:]}


def main():
    agent_md = (ROOT / "AGENT.md").read_text()
    client = ModelClient(model=MODEL, force_json=False, temperature=0.0, seed=3209,
                         num_ctx=8192, num_predict=700)
    res = client.complete([{"role": "system", "content": agent_md}, {"role": "user", "content": TASK}])
    code = extract_code(res.text)
    RAW.mkdir(parents=True, exist_ok=True)
    out = RAW / "generated_function.py"
    out.write_text(code)
    checks = run_checks(code)
    tests = run_tests(out)
    checks.append({"agent_md_rule": "tests run offline and pass", "pass": tests["own_tests_exit_code"] == 0,
                   "detail": tests["own_tests_stderr"] or "exit 0"})
    checks.append({"agent_md_rule": "independent behaviour check (13 / -13 / ValueError)",
                   "pass": tests["independent_tests_exit_code"] == 0,
                   "detail": tests["independent_tests_output"].strip()})
    result = {"timestamp": datetime.now().isoformat(timespec="seconds"), "model": MODEL,
              "task": TASK, "tokens": {"in": res.input_tokens, "out": res.output_tokens},
              "passed": sum(c["pass"] for c in checks), "total": len(checks), "checks": checks}
    (RAW / "agent_check.json").write_text(json.dumps(result, indent=2, default=str))
    print(f"AGENT.md compliance check | run by Ani Taraiya | model {MODEL}")
    print("-" * 70)
    print(code)
    print("-" * 70)
    for c in checks:
        print(f"[{'PASS' if c['pass'] else 'FAIL'}] {c['agent_md_rule']}")
    print(f"{result['passed']}/{result['total']} AGENT.md rules satisfied")


if __name__ == "__main__":
    main()
