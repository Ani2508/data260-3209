"""HW6 smoke test -> reports/hw06/verification.json   (run: make verify-hw06)

Expects the FastAPI backend on PORT_BASE 8509, MongoDB (s3209_doc) and Ollama running.
Never edits application code; test records/users it creates are removed at the end,
and file-memory checks run on temporary copies.
"""
import json
import random
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports" / "hw06"
OUT = HW / "verification.json"
BASE = "http://localhost:8509"
SID4, SEED, VERIFY_SEED = 3209, 3209, 263209
sys.path.insert(0, str(ROOT / "code" / "web_application"))

import config  # noqa: E402

rng = random.Random(VERIFY_SEED)
VERIFY_USER = f"verify_{VERIFY_SEED}_{rng.randint(1000, 9999)}"
state = {}


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


# ---------------------------------------------------------------- Part 1
def backend_up():
    r = requests.get(f"{BASE}/docs", timeout=5)
    return r.status_code == 200, f"GET /docs -> {r.status_code}"


def crud_roundtrip():
    url = f"{BASE}/api/doc/trials"
    c = requests.post(url, json={"title": f"Verify trial {VERIFY_SEED}", "phase": "phase_1",
                                 "start_date": "2027-01-01T09:00:00"}, timeout=5)
    tid = c.json()["id"]
    g = requests.get(f"{url}/{tid}", timeout=5)
    u = requests.put(f"{url}/{tid}", json={"status": "active"}, timeout=5)
    d = requests.delete(f"{url}/{tid}", timeout=5)
    gone = requests.get(f"{url}/{tid}", timeout=5)
    codes = [c.status_code, g.status_code, u.status_code, d.status_code, gone.status_code]
    ok = codes == [201, 200, 200, 204, 404] and c.json()["status"] == "recruiting" \
        and u.json()["status"] == "active"
    return ok, f"POST/GET/PUT/DELETE/GET -> {codes}, default status={c.json()['status']}"


def validation_errors():
    url = f"{BASE}/api/doc/trials"
    a = requests.post(url, json={"phase": "phase_1", "start_date": "2027-01-01"}, timeout=5)
    b = requests.post(url, json={"title": "x", "phase": "phase_9", "start_date": "2027-01-01"}, timeout=5)
    c = requests.post(url, json={"title": "x", "phase": "phase_1", "start_date": "soon"}, timeout=5)
    d = requests.get(f"{url}/not-an-id", timeout=5)
    codes = [a.status_code, b.status_code, c.status_code, d.status_code]
    has_msgs = all(r.json().get("errors") for r in (a, b, c))
    return codes == [422, 422, 422, 400] and has_msgs, f"missing/enum/type/bad id -> {codes}"


# ---------------------------------------------------------------- Part 2
def chat_replies():
    sid = f"{VERIFY_USER}-s1"
    msgs = ["My verification trial ID is NCT09990001.", "Our site is in Fresno.",
            "What is my trial ID?"]
    last = None
    for m in msgs:
        r = requests.post(f"{BASE}/api/chat", json={"user_id": VERIFY_USER, "session_id": sid,
                                                    "message": m}, timeout=600)
        r.raise_for_status()
        last = r.json()
    state["last"] = last
    ok = bool(last["reply"].strip()) and {"short_term", "long_term", "episodic_facts"} <= set(last["used"])
    return ok, f"reply {len(last['reply'])} chars, short-term={last['used']['short_term']['count']}"


def chat_usage_logged():
    u = state["last"]["usage"]
    keys = {"prompt_tokens", "completion_tokens", "system_primer_tokens", "long_term_tokens",
            "short_term_tokens", "episodic_tokens", "latency_ms"}
    return keys <= set(u) and u["prompt_tokens"] > 0, {k: u[k] for k in sorted(keys)}


def episodic_retrieval():
    facts = state["last"]["used"]["episodic_facts"]
    return len(facts) > 0 and all("score" in f for f in facts), f"{len(facts)} facts retrieved"


def memory_endpoint():
    m = requests.get(f"{BASE}/api/memory/{VERIFY_USER}", timeout=5).json()
    ok = {"recent_messages", "session_summary", "lifetime_summary", "episodic_facts"} <= set(m) \
        and len(m["recent_messages"]) == 6
    return ok, f"{len(m['recent_messages'])} messages, {len(m['episodic_facts'])} facts"


def aggregate_endpoint():
    a = requests.get(f"{BASE}/api/aggregate/{VERIFY_USER}", timeout=5).json()
    total = sum(d["messages"] for d in a["daily_message_counts"])
    return total == 6 and "recent_summaries" in a, f"daily counts={a['daily_message_counts']}"


# ---------------------------------------------------------------- Part 3 / 4 (offline)
def probes_file():
    d = yaml.safe_load(open(HW / "memory_probes.yaml"))
    ok = len(d["probes"]) == 5 and set(d["rubric"]) == {"1", "2", "3", "4", "5"}
    return ok, f"{len(d['probes'])} probes, rubric levels {sorted(d['rubric'])}"


def part3_raw():
    s = json.load(open(HW / "raw" / "part3_summary.json"))
    need = {"n4", "n12", "n30", "compress"}
    return need <= set(s), f"settings in summary: {sorted(s)}"


def consolidation_rules():
    import file_memory as fm
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "MEMORY.md"
        shutil.copy(HW / "memory_test" / "MEMORY_original.md", tmp)
        text = tmp.read_text()
        due, _ = fm.needs_consolidation(text)
        new_text, rep = fm.consolidate(text)
        ok = (len(text.splitlines()) == 55 and due and len(new_text.splitlines()) < 40
              and rep["duplicates_merged"] >= 3 and rep["contradictions_resolved"] >= 3
              and "Resolved contradictions" in new_text)
        return ok, (f"55 -> {len(new_text.splitlines())} lines, dup merged={rep['duplicates_merged']}, "
                    f"contradictions={rep['contradictions_resolved']}, suspect={len(rep['suspect_resolutions'])}")


def agent_md_rules():
    import file_memory as fm
    text = (ROOT / "AGENT.md").read_text()
    sections = [s for s in ("Project description", "Technology stack", "Coding conventions",
                            "Testing approach", "Prohibited actions") if f"## {s}" in text]
    bullets = [ln for ln in fm.content_lines(text) if ln.startswith("- ")]
    prompt = fm.build_system_prompt(fm.load_memory_files(), "base")
    ok = len(sections) >= 3 and len(bullets) >= 5 and "AGENT.md" in prompt and "MEMORY.md" in prompt
    return ok, f"{len(bullets)} instructions, categories={sections}"


def cleanup():
    from mongo_db import get_db
    db = get_db()
    n = sum(db[c].delete_many({"user_id": VERIFY_USER}).deleted_count
            for c in ("messages", "summaries", "episodes"))
    return True, f"removed {n} temporary docs for {VERIFY_USER}"


def main():
    random.seed(SEED)
    print(f"HW6 verification {datetime.now().isoformat(timespec='seconds')} | run by Ani Taraiya")
    checks = [check(n, f) for n, f in [
        ("FastAPI backend responds on PORT_BASE 8509", backend_up),
        ("MongoDB CRUD round trip on s3209_doc.trials", crud_roundtrip),
        ("Validation errors return 422/400 with messages", validation_errors),
        ("POST /api/chat returns a reply and the memory used", chat_replies),
        ("Per-request token/latency usage is reported", chat_usage_logged),
        ("Episodic facts are retrieved with similarity scores", episodic_retrieval),
        ("GET /api/memory/{user_id} returns messages, summaries, facts", memory_endpoint),
        ("GET /api/aggregate/{user_id} returns daily counts", aggregate_endpoint),
        ("memory_probes.yaml has 5 probes and a 1-5 rubric", probes_file),
        ("Part 3 raw summary covers all settings", part3_raw),
        ("MEMORY.md consolidation 55 -> <40 lines, explicit contradictions", consolidation_rules),
        ("AGENT.md has >=5 instructions in >=3 categories and is loaded", agent_md_rules),
    ]]
    check("Remove temporary verification data", cleanup)
    result = {
        "homework": "HW6", "sid4": SID4, "commit": commit_hash(),
        "model": f"{config.CHAT_MODEL} (Ollama, temperature 0, seed {SEED}); embeddings "
                 f"{state.get('last', {}).get('usage', {}).get('embed_backend', config.EMBED_MODEL)}",
        "config": {"SHORT_TERM_N": config.SHORT_TERM_N, "SUMMARIZE_EVERY_USER_MSGS":
                   config.SUMMARIZE_EVERY_USER_MSGS, "EPISODES_TOP_K": config.EPISODES_TOP_K,
                   "NUM_CTX": config.NUM_CTX},
        "seed": SEED, "verify_seed": VERIFY_SEED, "port_base": 8509, "prefix": "s3209",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "checks": checks, "passed": sum(c["pass"] for c in checks), "total": len(checks),
    }
    OUT.write_text(json.dumps(result, indent=2))
    print(f"{result['passed']}/{result['total']} checks passed -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
