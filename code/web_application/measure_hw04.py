import csv
import statistics
import time
from pathlib import Path

import requests

BASE = "http://localhost:8509"
EMAIL = "ani@sjsu.edu"
PASSWORD = "pass1234"
PAGE_SIZES = [10, 50, 200]
RUNS_PER_CONFIG = 30

OUT_DIR = Path(__file__).resolve().parents[2] / "reports" / "hw04" / "raw"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def login():
    s = requests.Session()
    r = s.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    r.raise_for_status()
    return s


def reset_counter(session):
    session.post(f"{BASE}/api/debug/reset-query-count").raise_for_status()


def get_counter(session):
    return session.get(f"{BASE}/api/debug/query-count").json()["queries"]


def measure(session, version, page_size):
    rows = []
    endpoint = f"{BASE}/api/trials/{version}/list?page_size={page_size}"

    for i in range(RUNS_PER_CONFIG):
        reset_counter(session)
        start = time.perf_counter()
        r = session.get(endpoint)
        elapsed_ms = (time.perf_counter() - start) * 1000
        r.raise_for_status()
        queries = get_counter(session)

        rows.append({
            "run": i + 1,
            "page_size": page_size,
            "version": version,
            "sql_queries": queries,
            "latency_ms": round(elapsed_ms, 2),
        })
        print(f"{version:6s} | page_size={page_size:3d} | run {i+1:2d}/30 "
              f"| queries={queries:3d} | {elapsed_ms:7.2f} ms")

    return rows


def percentile(data, pct):
    data = sorted(data)
    k = (len(data) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)


def summarize(rows):
    latencies = [r["latency_ms"] for r in rows]
    return {
        "sql_queries": rows[0]["sql_queries"],
        "p50": round(percentile(latencies, 50), 2),
        "p95": round(percentile(latencies, 95), 2),
        "p99": round(percentile(latencies, 99), 2),
    }


def main():
    session = login()
    all_rows = []
    summary_rows = []

    for version in ["naive", "fixed"]:
        for page_size in PAGE_SIZES:
            rows = measure(session, version, page_size)
            all_rows.extend(rows)
            summary = summarize(rows)
            summary_rows.append({
                "page_size": page_size,
                "version": version,
                "sql_stmts_per_req": summary["sql_queries"],
                "p50_ms": summary["p50"],
                "p95_ms": summary["p95"],
                "p99_ms": summary["p99"],
            })

    raw_path = OUT_DIR / "n_plus_1_raw.csv"
    with open(raw_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)

    summary_path = OUT_DIR / "n_plus_1_summary.csv"
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nSaved {len(all_rows)} raw rows to {raw_path}")
    print(f"Saved summary table to {summary_path}")
    for row in summary_rows:
        print(row)


if __name__ == "__main__":
    main()