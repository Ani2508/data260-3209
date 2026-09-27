import json
import subprocess
import sys
import time
from pathlib import Path

import requests

BASE = "http://localhost:8509"
EMAIL = "verify_hw04@sjsu.edu"
PASSWORD = "verifypass123"
SID4 = 3209
SEED = 3209
VERIFY_SEED = 263209

OUT_PATH = Path(__file__).resolve().parents[2] / "reports" / "hw04" / "verification.json"


def get_commit_hash():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2]
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def run_checks():
    checks = []

    # Check 1: backend responds on PORT_BASE
    try:
        r = requests.get(f"{BASE}/docs", timeout=5)
        checks.append({"check": "Backend responds on PORT_BASE 8509", "pass": r.status_code == 200})
    except Exception as e:
        checks.append({"check": "Backend responds on PORT_BASE 8509", "pass": False, "error": str(e)})

    # Check 2: can register a temp user (created fresh each run, then used only)
    session = requests.Session()
    try:
        r = session.post(f"{BASE}/api/auth/register",
                          json={"name": "Verify Bot", "email": EMAIL, "password": PASSWORD})
        ok = r.status_code in (201, 409)  # 409 = already exists from a previous run, still fine
        checks.append({"check": "Register endpoint works", "pass": ok})
    except Exception as e:
        checks.append({"check": "Register endpoint works", "pass": False, "error": str(e)})

    # Check 3: login works and sets a session cookie
    try:
        r = session.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        ok = r.status_code == 200 and "session_token" in session.cookies
        checks.append({"check": "Login sets HTTP-only session cookie", "pass": ok})
    except Exception as e:
        checks.append({"check": "Login sets HTTP-only session cookie", "pass": False, "error": str(e)})

    # Check 4: naive list endpoint returns data
    try:
        r = session.get(f"{BASE}/api/trials/naive/list?page_size=5")
        data = r.json()
        ok = r.status_code == 200 and isinstance(data, list) and len(data) > 0
        checks.append({"check": "Naive list endpoint returns data", "pass": ok})
    except Exception as e:
        checks.append({"check": "Naive list endpoint returns data", "pass": False, "error": str(e)})

    # Check 5: fixed list endpoint returns data
    try:
        r = session.get(f"{BASE}/api/trials/fixed/list?page_size=5")
        data = r.json()
        ok = r.status_code == 200 and isinstance(data, list) and len(data) > 0
        checks.append({"check": "Fixed list endpoint returns data", "pass": ok})
    except Exception as e:
        checks.append({"check": "Fixed list endpoint returns data", "pass": False, "error": str(e)})

    # Check 6: CRUD create works (temporary test record, not touching real app code)
    try:
        r = session.post(f"{BASE}/api/trials", json={"trialTitle": "Verify Smoke Test", "sponsor": "Verify Sponsor"})
        ok = r.status_code == 201
        new_id = r.json().get("id") if ok else None
        checks.append({"check": "Create trial (POST) works", "pass": ok})

        # clean up the temp record so this script never modifies real data permanently
        if new_id:
            session.delete(f"{BASE}/api/trials/{new_id}")
    except Exception as e:
        checks.append({"check": "Create trial (POST) works", "pass": False, "error": str(e)})

    # Check 7: blocked without login (log out first)
    try:
        session.post(f"{BASE}/api/auth/logout")
        r = requests.get(f"{BASE}/api/trials")  # fresh, unauthenticated session
        ok = r.status_code == 401
        checks.append({"check": "Trials endpoint blocked without login", "pass": ok})
    except Exception as e:
        checks.append({"check": "Trials endpoint blocked without login", "pass": False, "error": str(e)})

    return checks


def main():
    checks = run_checks()
    all_passed = all(c["pass"] for c in checks)

    result = {
        "homework": "DATA-260 HW4",
        "SID4": SID4,
        "commit_hash": get_commit_hash(),
        "model_configuration": "qwen3:4b-instruct-2507-q4_K_M via Ollama (documented substitute)",
        "SEED": SEED,
        "VERIFY_SEED": VERIFY_SEED,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "checks": checks,
        "all_checks_passed": all_passed,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))
    print(f"\nSaved to {OUT_PATH}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()