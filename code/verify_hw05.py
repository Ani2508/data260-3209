"""HW5 smoke test -> reports/hw05/verification.json   (run: make verify-hw05)

Starts nothing permanent and never edits application code. Expects the FastAPI
backend on PORT_BASE 8509 and MySQL (s3209_rel) to be running.
"""
import asyncio
import json
import random
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = ROOT / "code" / "mcp_servers"
OUT = ROOT / "reports" / "hw05" / "verification.json"
BASE = "http://localhost:8509"
SID4, SEED, VERIFY_SEED = 3209, 3209, 263209
sys.path.insert(0, str(MCP_DIR))


def commit_hash():
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT)
    return r.stdout.strip() or "unknown"


def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as exc:
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    print(f"[{'PASS' if ok else 'FAIL'}] {name} - {detail}")
    return {"check": name, "pass": bool(ok), "detail": str(detail)[:300]}


# ---------------------------------------------------------------- backend checks
session = requests.Session()


def backend_up():
    r = requests.get(f"{BASE}/docs", timeout=5)
    return r.status_code == 200, f"GET /docs -> {r.status_code}"


def login():
    email = f"verify_{uuid.uuid4().hex[:6]}@sjsu.edu"          # temporary test user
    session.post(f"{BASE}/api/auth/register", json={"name": "Verify Bot", "email": email,
                                                    "password": "verifypass123"}, timeout=5)
    r = session.post(f"{BASE}/api/auth/login", json={"email": email, "password": "verifypass123"}, timeout=5)
    return r.status_code == 200 and "session_token" in session.cookies, f"login -> {r.status_code}"


def sponsors_paged():
    r = session.get(f"{BASE}/api/sponsors", params={"page": 1, "page_size": 3}, timeout=5)
    body = r.json()
    ok = r.status_code == 200 and {"items", "total", "page", "page_size"} <= set(body)
    return ok, f"{r.status_code}, total={body.get('total')}"


def relationship_query():
    first = session.get(f"{BASE}/api/sponsors", params={"page_size": 1}, timeout=5).json()["items"][0]
    r = session.get(f"{BASE}/api/sponsors/{first['id']}/trials", timeout=5)
    ok = r.status_code == 200 and all(t["sponsor_id"] == first["id"] for t in r.json())
    return ok, f"sponsor {first['id']} -> {len(r.json())} trials"


def validation_and_conflict():
    bad = session.post(f"{BASE}/api/trials", json={"trial_title": "x", "nct_id": "BAD",
                                                   "sponsor_id": 1}, timeout=5)
    sid = session.get(f"{BASE}/api/sponsors", params={"page_size": 1}, timeout=5).json()["items"][0]["id"]
    conflict = session.delete(f"{BASE}/api/sponsors/{sid}", timeout=5)
    ok = bad.status_code == 422 and conflict.status_code == 409
    return ok, f"bad NCT -> {bad.status_code}, delete sponsor with trials -> {conflict.status_code}"


# ---------------------------------------------------------------- MCP checks
async def _mcp(server_file, tool=None, args=None):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=sys.executable, args=[server_file], cwd=str(MCP_DIR))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as s:
            await s.initialize()
            names = sorted(t.name for t in (await s.list_tools()).tools)
            result = None
            if tool:
                res = await s.call_tool(tool, args or {})
                result = json.loads(res.content[0].text)
            return names, result


def meals_server():
    names, _ = asyncio.run(asyncio.wait_for(_mcp("meals_server.py"), 30))
    want = ["meal_details", "meals_by_ingredient", "random_meal", "search_meals_by_name"]
    return names == want, f"tools={names}"


def trials_server():
    names, env = asyncio.run(asyncio.wait_for(_mcp("trials_server.py", "trial_stats",
                                                   {"group_by": "status"}), 30))
    ok = names == ["get_trial", "search_trials", "trial_stats"] and env["ok"] is True \
        and set(env) == {"ok", "data", "error"}
    return ok, f"tools={names}, trial_stats ok={env['ok']}"


def trials_server_rejects():
    _, env = asyncio.run(asyncio.wait_for(_mcp("trials_server.py", "get_trial", {"trial_id": 999999}), 30))
    ok = env["ok"] is False and env["data"] is None and "not found" in str(env["error"])
    return ok, env["error"]


# ---------------------------------------------------------------- offline checks
def offline_tests():
    r = subprocess.run([sys.executable, "test_tools.py"], capture_output=True, text=True, cwd=MCP_DIR)
    last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
    return r.returncode == 0, last


def seeded_faults_reproducible():
    from resilience import FaultyStore, TransientError

    class Null:
        def get(self, *a):
            return {}

    def sequence():
        fs, out = FaultyStore(Null(), 0.5, seed=VERIFY_SEED, latency_s=0), []
        for _ in range(50):
            try:
                fs.get(1); out.append(1)
            except TransientError:
                out.append(0)
        return out
    a, b = sequence(), sequence()
    return a == b, f"same 50-call sequence twice, failures={a.count(0)}"


def safety_rule():
    from tool_gateway import execute_tool
    env = json.loads(execute_tool("search_trials", {"query": "asthma MRN 12345"}, store=object()))
    return env["ok"] is False and env["error"].startswith("blocked by safety rule"), env["error"][:80]


def main():
    random.seed(SEED)
    print(f"HW5 verification {datetime.now().isoformat(timespec='seconds')}")
    checks = [check(n, f) for n, f in [
        ("FastAPI backend responds on PORT_BASE 8509", backend_up),
        ("Register + login sets session cookie", login),
        ("Sponsors list is paginated", sponsors_paged),
        ("Relationship endpoint returns only that sponsor's trials", relationship_query),
        ("Validation (422) and delete-protection (409)", validation_and_conflict),
        ("meals MCP server starts and lists its 4 tools", meals_server),
        ("s3209_trials MCP server answers a tool call with {ok,data,error}", trials_server),
        ("s3209_trials MCP server rejects an invalid call cleanly", trials_server_rejects),
        ("Offline test suite passes", offline_tests),
        ("Fault injection is reproducible with VERIFY_SEED", seeded_faults_reproducible),
        ("Safety rule blocks patient-identifying input", safety_rule),
    ]]
    result = {
        "homework": "HW5", "sid4": SID4, "commit": commit_hash(),
        "model": "llama3.1:8b (Ollama, temperature 0, seed 3209)",
        "seed": SEED, "verify_seed": VERIFY_SEED, "port_base": 8509, "prefix": "s3209",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"{result['passed']}/{result['total']} checks passed -> {OUT.relative_to(ROOT)}")
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
