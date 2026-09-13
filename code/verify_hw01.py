"""
verify_hw01.py — self-check for HW1 (writes reports/hw01/verification.json).
Run from the repo root:  py -3.12 verify_hw01.py
"""
import os, json, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
def path(*p): return os.path.join(HERE, *p)
def exists(rel): return os.path.exists(path(*rel.split("/")))

checks, details = {}, {}

# Code files (new structure: code/ and src/)
checks["agents_demo_present"]  = exists("code/agents_demo.py")
checks["hw1_client_present"]   = exists("code/hw1_client.py")
checks["run_nondeterminism_present"] = exists("code/run_nondeterminism.py")
checks["model_client_at_src"]  = exists("src/model_client.py")
checks["agent_md_at_root"]     = exists("AGENT.md")
checks["domain_schema_at_root"]= exists("DOMAIN_SCHEMA.md")

# Web application files
for f in ["index.html", "app.js", "styles.css", "nginx.conf"]:
    checks[f"webapp_{f.replace('.', '_')}_present"] = exists(f"code/web_application/{f}")
checks["dockerfile_present"] = exists("code/Dockerfile")

# Nginx listens on 8509
if exists("code/web_application/nginx.conf"):
    txt = open(path("code","web_application","nginx.conf"), encoding="utf-8").read()
    checks["app_listens_on_8509"] = "listen" in txt and "8509" in txt
else:
    checks["app_listens_on_8509"] = False

# Non-determinism input valid
if exists("reports/hw01/cases/nondeterminism_input.json"):
    try:
        d = json.load(open(path("reports","hw01","cases","nondeterminism_input.json"), encoding="utf-8"))
        checks["nd_input_valid"] = bool(d.get("title")) and bool(d.get("content"))
    except Exception as e:
        checks["nd_input_valid"] = False; details["nd_input_error"] = str(e)
else:
    checks["nd_input_valid"] = False

# 40-run CSV
if exists("reports/hw01/raw/nondeterminism_runs.csv"):
    lines = [l for l in open(path("reports","hw01","raw","nondeterminism_runs.csv"), encoding="utf-8").read().splitlines() if l.strip()]
    rows = max(0, len(lines) - 1)
    checks["nd_runs_csv_has_40_rows"] = rows == 40
    details["nd_runs_row_count"] = rows
else:
    checks["nd_runs_csv_has_40_rows"] = False; details["nd_runs_row_count"] = 0

# Adapter interface
if exists("src/model_client.py"):
    mc = open(path("src","model_client.py"), encoding="utf-8").read()
    checks["adapter_defines_complete"] = bool(re.search(r"def complete\s*\(", mc))
    checks["adapter_counts_tokens"] = "input_tokens" in mc and "output_tokens" in mc
else:
    checks["adapter_defines_complete"] = False; checks["adapter_counts_tokens"] = False

# Tags derived from input
if exists("code/agents_demo.py"):
    checks["tags_derived_from_input"] = "phrase_candidates" in open(path("code","agents_demo.py"), encoding="utf-8").read()
else:
    checks["tags_derived_from_input"] = False

passed = sum(1 for v in checks.values() if v); total = len(checks)
result = {
    "summary": {"passed": passed, "total": total, "all_passed": passed == total},
    "checks": checks, "details": details,
    "config": {"SID4":3209,"PORT_BASE":8509,"PREFIX":"s3209","SEED":3209,
               "VERIFY_SEED":263209,"DOMAIN_ID":1,"domain":"Clinical trial listings"},
    "model": "qwen3:8b (Ollama, CPU-only, /no_think)",
}
os.makedirs(path("reports","hw01"), exist_ok=True)
outp = path("reports","hw01","verification.json")
json.dump(result, open(outp,"w",encoding="utf-8"), indent=2)
print(f"Verification: {passed}/{total} checks passed")
for k,v in checks.items(): print(f"  [{'PASS' if v else 'FAIL'}] {k}")
print(f"\nWrote {outp}")
sys.exit(0 if passed==total else 1)
