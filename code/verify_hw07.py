"""HW7 smoke test -> reports/hw07/verification.json   (run: make verify-hw07)

Expects the FastAPI backend on PORT_BASE 8509 (make run-api), MySQL s3209_rel with the
HW7 users (make hw07-migrate) and Ollama with llama3.1:8b and qwen3:8b.
Never edits application code: agent logs and reflections go to a temporary folder, the
file-tool checks run in a temporary sandbox, and the trial the RBAC check creates is deleted.
"""
from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports" / "hw07"
OUT = HW / "verification.json"
BASE = "http://localhost:8509"
SID4, SEED, VERIFY_SEED = 3209, 3209, 263209
for sub in ("code", "code/mcp_servers", "code/web_application"):
    sys.path.insert(0, str(ROOT / sub))
load_dotenv(ROOT / ".env")
PW = os.environ.get("HW7_DEMO_PASSWORD", "")
TMP = Path(tempfile.mkdtemp(prefix="verify_hw07_"))
state: dict = {}


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT)
    return r.stdout.rstrip("\n")


def check(part: str, name: str, fn) -> dict:
    t0 = time.perf_counter()
    try:
        ok, detail = fn()
    except Exception as exc:
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    secs = round(time.perf_counter() - t0, 1)
    print(f"[{'PASS' if ok else 'FAIL'}] {part} {name} - {detail} ({secs}s)")
    return {"part": part, "check": name, "pass": bool(ok), "detail": str(detail)[:300],
            "seconds": secs}


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=600)


def serve(folder: Path, port: int) -> http.server.ThreadingHTTPServer:
    """Serve a folder on 127.0.0.1 only (local copies of the pricing pages)."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ---------------------------------------------------------------- Part 1
def login(user: str, password: str) -> requests.Response:
    return requests.post(f"{BASE}/auth/login", json={"username": user, "password": password},
                         timeout=10)


def login_codes():
    good, bad = login("s3209_writer", PW), login("s3209_writer", "wrong-password")
    token = good.json().get("access_token", "") if good.status_code == 200 else ""
    ok = good.status_code == 200 and token.count(".") == 2 and bad.status_code == 401
    return ok, f"valid -> {good.status_code} (JWT {len(token)} chars), invalid -> {bad.status_code}"


def me_codes():
    tok = {r: login(f"s3209_{r}", PW).json()["access_token"]
           for r in ("reader", "writer", "moderator")}
    state["tok"] = tok
    none = requests.get(f"{BASE}/auth/me", timeout=10)
    forged = requests.get(f"{BASE}/auth/me", timeout=10,
                          headers={"Authorization": "Bearer abc.def.ghi"})
    good = requests.get(f"{BASE}/auth/me", timeout=10,
                        headers={"Authorization": f"Bearer {tok['reader']}"})
    role = good.json().get("role") if good.status_code == 200 else None
    codes = [none.status_code, forged.status_code, good.status_code]
    return codes == [401, 401, 200] and role == "reader", \
        f"no token / forged / valid -> {codes}, role={role}"


def rbac_codes():
    h = {r: {"Authorization": f"Bearer {t}"} for r, t in state["tok"].items()}
    sp = requests.get(f"{BASE}/api/sponsors?page_size=1", headers=h["reader"], timeout=10)
    body = {"trial_title": f"HW7 verify {VERIFY_SEED}", "nct_id": f"NCT{VERIFY_SEED:08d}",
            "enrollment_slots": 10, "status": "Recruiting",
            "sponsor_id": sp.json()["items"][0]["id"]}
    lst = requests.get(f"{BASE}/api/trials?page_size=2", headers=h["reader"], timeout=10)
    c_reader = requests.post(f"{BASE}/api/trials", json=body, headers=h["reader"], timeout=10)
    c_writer = requests.post(f"{BASE}/api/trials", json=body, headers=h["writer"], timeout=10)
    codes = [lst.status_code, c_reader.status_code, c_writer.status_code]
    if c_writer.status_code == 201:
        url = f"{BASE}/api/trials/{c_writer.json()['id']}"
        codes.append(requests.delete(url, headers=h["writer"], timeout=10).status_code)
        codes.append(requests.delete(url, headers=h["moderator"], timeout=10).status_code)
    ok = codes[:4] == [200, 403, 201, 403] and len(codes) == 5 and codes[4] in (200, 204)
    return ok, ("list reader / create reader / create writer / delete writer / delete "
                f"moderator -> {codes}")


def hashed_passwords():
    from database import engine
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT username, password_hash, role FROM users "
                                    "WHERE username LIKE 's3209%%'").all()
    ok = len(rows) >= 3 and all(r[1].startswith("$2") and r[1] != PW for r in rows) \
        and {r[2] for r in rows} >= {"reader", "writer", "moderator"}
    return ok, f"{len(rows)} users, bcrypt hashes={all(r[1].startswith('$2') for r in rows)}"


def lint_clean():
    """Run the pre-commit Ruff hook on every Python file added or changed since the hw6 tag."""
    files = git("diff", "--name-only", "--diff-filter=AM", "hw6", "HEAD", "--",
                "code/*.py", "src/*.py").split()
    pc = ROOT / ".venv" / "bin" / "pre-commit"
    r = run([str(pc) if pc.exists() else "pre-commit", "run", "ruff", "--files", *files], ROOT)
    last = (r.stdout.strip().splitlines() or ["(no output)"])[0]
    return r.returncode == 0 and len(files) > 0, \
        f"pre-commit ruff hook on {len(files)} HW7 files -> {last.split('.')[-1].strip()}"


# ---------------------------------------------------------------- Part 2
def part2_offline_tests():
    r = run([sys.executable, "test_agent_loop.py"], ROOT / "code" / "mcp_servers")
    passed = r.stdout.count("PASS")
    return r.returncode == 0 and passed > 0, \
        f"test_agent_loop.py exit {r.returncode}, {passed} PASS"


def part2_task_a():
    from agent_loop import AdapterModel, run_agent
    from reflexion import ground_truth, task_list, verify
    task = task_list()["A"]
    res = run_agent(task["prompt"], model=AdapterModel(temperature=0.0), log=lambda s: None,
                    log_path=TMP / "agent_runs.jsonl")
    names = [c["name"] for c in res.tool_calls if c["ok"]]
    v = verify("A", res, ground_truth())
    ok = res.stop_reason == "final_answer" and names[:2] == task["expected_chain"] and v["passed"]
    return ok, f"tools {names}, stop={res.stop_reason}, verifier passed={v['passed']}"


def part2_bad_id():
    from agent_loop import AdapterModel, run_agent
    from tool_gateway import execute_tool
    env = json.loads(execute_tool("get_trial", {"trial_id": 99999}))
    res = run_agent("Show me the full details of trial 99999.",
                    model=AdapterModel(temperature=0.0), log=lambda s: None,
                    log_path=TMP / "agent_runs.jsonl")
    ok = env["ok"] is False and bool(env.get("error")) and bool(res.stop_reason)
    return ok, f"execute_tool -> ok=false ({env.get('error')}); agent stop={res.stop_reason}"


# ---------------------------------------------------------------- Part 3
def part3_offline_tests():
    r = run([sys.executable, "test_reflexion.py"], ROOT / "code" / "mcp_servers")
    passed = r.stdout.count("PASS")
    return r.returncode == 0 and passed > 0, \
        f"test_reflexion.py exit {r.returncode}, {passed} PASS"


def part3_reflexion_run():
    import reflexion as rx
    task = rx.task_list()["B"]
    rr = rx.run_reflexion("B", task["prompt"], rx.ground_truth(), log=lambda s: None,
                          store=rx.ReflectionStore(TMP / "reflections.jsonl"),
                          agent_log_path=TMP / "reflexion_runs.jsonl")
    ok = (rr.stop_reason in ("success", "budget_exhausted", "human_review")
          and rr.retries <= rx.MAX_RETRIES and rr.tool_calls <= rx.TOOL_BUDGET)
    return ok, (f"task B stop={rr.stop_reason}, retries={rr.retries}/{rx.MAX_RETRIES}, "
                f"tool calls={rr.tool_calls}/{rx.TOOL_BUDGET}, tokens={rr.tokens}")


# ---------------------------------------------------------------- Part 4 / 5
def part4_tools():
    from bikeshare import tools as T
    T.DEFENSES.update({"prompt": True, "tool": True})
    db = T.TripDB(HW / "cases" / "part4_scenarioA_trips.csv")
    n = T.csv_sql(db, "SELECT COUNT(*) AS n FROM trips")
    calc = T.calculator("2*(3+4)")
    bad = T.calculator("__import__('os')")
    shape = {"success", "ts"} <= set(n) and {"rows", "row_count", "source"} <= set(n["data"])
    rows = n["data"]["rows"][0]["n"]
    ok = shape and rows >= 500 and calc["data"]["value"] == 14 and not bad["success"]
    return ok, f"csv_sql rows={rows}, calculator 2*(3+4)={calc['data']['value']}, " \
               f"injection rejected={not bad['success']}"


def part4_snapshots():
    out = []
    for s in ("A", "B"):
        d = HW / "raw" / f"part4_scenario{s}"
        meta = json.loads((d / "pricing_snapshot.json").read_text())
        sha = hashlib.sha256((d / "pricing_snapshot.txt").read_text().encode()).hexdigest()
        out.append(sha == meta["sha256"] and bool(meta.get("url"))
                   and bool(meta.get("accessed_at")))
    return all(out), f"snapshot SHA-256 matches saved hash: A={out[0]}, B={out[1]}"


def part4_agent_b():
    from bikeshare.agent import run_bike_agent
    srv = serve(HW / "raw" / "part4_scenarioB", 8598)
    try:
        r = run_bike_agent(HW / "cases" / "part4_scenarioB_trips.csv",
                           "http://127.0.0.1:8598/pricing_snapshot.txt")
    finally:
        srv.shutdown()
    m = r["metrics"]
    ok = r["decision"] == "Pay Per Ride/Minute" and m["stop_reason"] == "final_answer"
    return ok, f"scenario B decision={r['decision']}, steps={m['steps']}, stop={m['stop_reason']}"


def part5_defenses():
    from bikeshare import tools as T
    T.DEFENSES.update({"prompt": True, "tool": True})
    db = T.TripDB(HW / "cases" / "part4_scenarioB_trips.csv")
    before = T.csv_sql(db, "SELECT COUNT(*) AS n FROM trips")["data"]["rows"][0]["n"]
    d = T.csv_sql(db, "DELETE FROM trips")
    two = T.csv_sql(db, "SELECT 1; DROP TABLE trips")
    after = T.csv_sql(db, "SELECT COUNT(*) AS n FROM trips")["data"]["rows"][0]["n"]
    srv = serve(HW / "cases", 8597)
    try:
        p = T.policy_retriever(T.PageCache(), "http://127.0.0.1:8597/part5_hostile_pricing.html",
                               "membership price")
    finally:
        srv.shutdown()
    labelled = p["success"] and all(x["text"].startswith("<untrusted_page_text>")
                                    for x in p["data"]["passages"])
    ok = not d["success"] and not two["success"] and before == after and labelled
    return ok, (f"DELETE rejected={not d['success']}, stacked rejected={not two['success']}, "
                f"rows {before}->{after}, retrieved text labelled untrusted={labelled}")


# ---------------------------------------------------------------- Part 6
def part6_gate():
    from devtools.safety_gate import SAFE_PREFIXES, confirm_bash, is_destructive
    safe = ["ls -la", "cat app.py", "grep -rn DEBUG .", "python3 -m py_compile app.py",
            "git status"]
    bad = ["rm -rf build", "sudo rm /tmp/x", "chmod -R 777 .", "dd if=/dev/zero of=/dev/disk2",
           "echo pwned > /etc/hosts"]
    ok_safe = all(confirm_bash(c)["allowed"] for c in safe)
    ok_bad = all(is_destructive(c) and not confirm_bash(c)["allowed"] for c in bad)
    confirmed = confirm_bash("rm -rf build", auto_approve=True)["allowed"]
    ok = ok_safe and ok_bad and confirmed and "echo" in SAFE_PREFIXES
    return ok, f"5 safe allowed={ok_safe}, 5 destructive blocked={ok_bad}, " \
               f"allowed with confirmation={confirmed}"


def part6_file_tools():
    from devtools.file_tools import FileTools
    box = TMP / "sandbox"
    box.mkdir()
    t = FileTools(box)
    t.write_file("app.py", "DEBUG = True\nx = 1\n")
    t.write_file("utils.py", "def f():\n    return 1\n")
    found = t.search_in_files("DEBUG", file_pattern="*.py")["data"]["files"]
    first = t.read_file("app.py", max_lines=1)["data"]["lines_returned"]
    diff = t.edit_file("app.py", "DEBUG = True", "DEBUG = False")["data"]["diff"]
    escape = t.read_file("../outside.txt")["success"]
    gated = t.bash("rm -rf .")["success"]
    ok = (t.glob_files("*.py")["data"]["count"] == 2 and found == ["app.py"] and first == 1
          and "+DEBUG = False" in diff and not escape and not gated)
    return ok, f"glob 2 files, search -> {found}, max_lines=1 -> {first}, diff ok, " \
               f"sandbox escape refused={not escape}, rm -rf blocked={not gated}"


CHECKS = [
    ("Part 1", "POST /auth/login: token for valid, 401 for invalid credentials", login_codes),
    ("Part 1", "GET /auth/me: 401 without / with forged token, 200 with role", me_codes),
    ("Part 1", "RBAC on /api/trials: read any role, create writer+, delete moderator", rbac_codes),
    ("Part 1", "MySQL users table stores only bcrypt hashes and the three roles", hashed_passwords),
    ("Part 1", "Ruff pre-commit hook passes on all HW7 Python files", lint_clean),
    ("Part 2", "Agent loop offline tests (repair path, ceilings, logging)", part2_offline_tests),
    ("Part 2", "run_agent completes task A (search -> get_trial) and passes verifier",
     part2_task_a),
    ("Part 2", "Nonexistent id: useful tool error, agent stops without crashing", part2_bad_id),
    ("Part 3", "Reflexion offline tests (verifier, store isolation, sanitizing)",
     part3_offline_tests),
    ("Part 3", "Reflexion run on task B stops cleanly within retry/tool budgets",
     part3_reflexion_run),
    ("Part 4", "csv_sql / calculator return the common envelope and correct values", part4_tools),
    ("Part 4", "Saved pricing snapshots match their SHA-256 hashes", part4_snapshots),
    ("Part 4", "Bike-share agent recommends pay-per-use for scenario B", part4_agent_b),
    ("Part 5", "Tool boundary rejects writes; retrieved text labelled untrusted", part5_defenses),
    ("Part 6", "Safety gate: 5 safe allowed, 5 destructive blocked unless confirmed", part6_gate),
    ("Part 6", "File tools in a temp sandbox (glob, search, read, edit diff, escape)",
     part6_file_tools),
]


def main() -> None:
    print("\n================ HW7 verification (make verify-hw07) ================")
    print(f"Run by: Ani Taraiya (s3209)   commit {git('rev-parse', '--short', 'HEAD')}   "
          f"temp folder: {TMP}")
    changed = [ln[3:] for ln in git("status", "--porcelain").splitlines()
               if not ln[3:].startswith("reports/")]
    results = [check(p, n, f) for p, n, f in CHECKS]
    report = {
        "homework": "HW7",
        "sid4": SID4,
        "commit": git("rev-parse", "HEAD"),
        "code_matches_commit": not changed,
        "model": {"agent_loop_and_reflexion": "llama3.1:8b (Ollama via src/model_client.py, "
                                              "temperature 0, seed 3209, num_ctx 8192)",
                  "bikeshare_agent": "qwen3:8b (Ollama, LangChain create_agent, temperature 0)"},
        "config": {"port_base": 8509, "prefix": "s3209", "domain_id": 1,
                   "domain": "Clinical trial listings", "database": "MySQL s3209_rel",
                   "jwt": "HS256 bearer, roles reader/writer/moderator"},
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "checks": results,
        "passed": sum(r["pass"] for r in results),
        "total": len(results),
    }
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\n  {report['passed']}/{report['total']} checks passed   "
          f"code matches commit: {report['code_matches_commit']}")
    print("  wrote reports/hw07/verification.json")


if __name__ == "__main__":
    main()
