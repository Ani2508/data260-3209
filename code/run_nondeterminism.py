"""
run_nondeterminism.py — Part 3 experiment.

Runs the Planner -> Reviewer -> Finalizer pipeline on ONE fixed input:
  - 20 times at temperature 0.0
  - 20 times at temperature 0.7
(40 runs total)

For each run it records the FINAL tag set and the wall-clock latency (ms),
appending to a CSV in reports/hw01/raw/ immediately (crash-safe). The script is
RESUMABLE: on restart it counts completed runs per temperature and only runs
what's missing. At the end it computes and prints the metrics tables.

Whole pipeline runs at the run's temperature (as the assignment states:
"run the pipeline ... at temperature X"). Reasoning disabled (/no_think) for
practical speed on CPU; this change is documented in the report.
"""

import os, sys, json, csv, time, statistics
from typing import List, Dict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from model_client import ModelClient  # noqa: E402
import agents_demo as ad              # reuse the exact pipeline logic

HERE = os.path.dirname(os.path.abspath(__file__))
# reports/ lives at the repo root, one level up from code/
ROOT = os.path.abspath(os.path.join(HERE, ".."))
INPUT_PATH = os.path.join(ROOT, "reports", "hw01", "cases", "nondeterminism_input.json")
RAW_DIR = os.path.join(ROOT, "reports", "hw01", "raw")
CSV_PATH = os.path.join(RAW_DIR, "nondeterminism_runs.csv")

RUNS_PER_TEMP = 20
TEMPS = [0.0, 0.7]


def load_input():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        d = json.load(f)
    return d["title"], d["content"]


def run_pipeline_once(title: str, content: str, temperature: float) -> Dict:
    """One full Planner->Reviewer->Finalizer pass at the given temperature.
    Returns the final tags + latency in ms."""
    client = ModelClient(temperature=temperature, force_json=True)

    planner = ad.SimpleAgent("Planner",
        "Propose exactly 3 distinct, topical tags (prefer multi-word phrases) and a "
        "one-line summary (<=25 words) for the given title and content. Derive tags "
        "from the input text only.", client)
    reviewer = ad.SimpleAgent("Reviewer",
        "Validate the planner's tags and summary: tags topical and specific, summary "
        "<=25 words, no code or markdown. List problems in data.issues; otherwise echo "
        "cleaned tags/summary.", client)
    finalizer = ad.SimpleAgent("Finalizer",
        "Use the reviewer feedback to finalize. Output exactly 3 tags in data.tags and "
        "the final summary in data.summary. Set data.issues to [].", client)

    task = (f'Given title "{title}" and content "{content}", produce exactly 3 topical '
            f'tags and a one-sentence summary (<=25 words) in your own words.')

    t0 = time.time()
    transcript: List[Dict[str, str]] = []
    a = planner.respond(transcript, task, title, content, strict=True)
    transcript.append({"role": "Planner", "content": a.get("message", "")})
    b = reviewer.respond(transcript, task, title, content, strict=True)
    transcript.append({"role": "Reviewer", "content": b.get("message", "")})
    final = finalizer.respond(transcript, task, title, content, strict=True)
    latency_ms = int((time.time() - t0) * 1000)

    tags = final.get("data", {}).get("tags", [])
    return {"tags": tags, "latency_ms": latency_ms}


def completed_counts() -> Dict[float, int]:
    """Count runs already saved per temperature (for resume)."""
    counts = {t: 0 for t in TEMPS}
    if not os.path.exists(CSV_PATH):
        return counts
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                counts[float(row["temperature"])] += 1
            except Exception:
                pass
    return counts


def append_row(run_index, temperature, tags, latency_ms):
    os.makedirs(RAW_DIR, exist_ok=True)
    new = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["run_index", "temperature", "tag1", "tag2", "tag3",
                        "tags_joined", "latency_ms", "timestamp"])
        t = (tags + ["", "", ""])[:3]
        w.writerow([run_index, temperature, t[0], t[1], t[2],
                    " | ".join(tags), latency_ms,
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())])


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)


def compute_metrics():
    """Read the CSV and print the assignment's metric tables per temperature."""
    if not os.path.exists(CSV_PATH):
        print("No results yet.")
        return
    by_temp = {t: [] for t in TEMPS}
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            temp = float(row["temperature"])
            by_temp.setdefault(temp, []).append({
                "tags": tuple(t for t in [row["tag1"], row["tag2"], row["tag3"]] if t),
                "latency": int(row["latency_ms"]),
            })

    print("\n================ PART 3 METRICS ================")
    for temp in TEMPS:
        runs = by_temp.get(temp, [])
        if not runs:
            print(f"\nTemp {temp}: no runs yet.")
            continue
        tagsets = [r["tags"] for r in runs]
        distinct = len(set(tagsets))

        # tags appearing in ALL runs vs EXACTLY ONE run
        from collections import Counter
        run_presence = Counter()
        for ts in tagsets:
            for tag in set(ts):
                run_presence[tag] += 1
        in_all = [tag for tag, c in run_presence.items() if c == len(runs)]
        in_one = [tag for tag, c in run_presence.items() if c == 1]

        lat = [r["latency"] for r in runs]
        print(f"\n--- Temp {temp}  ({len(runs)} runs) ---")
        print(f"Distinct tag sets   : {distinct}")
        print(f"Tags in all runs    : {in_all or '(none)'}")
        print(f"Tags in exactly 1   : {in_one or '(none)'}")
        print(f"Latency p50/p95/p99 : {pct(lat,50)} / {pct(lat,95)} / {pct(lat,99)} ms")
    print("\n===============================================")


def main():
    title, content = load_input()
    print(f"Fixed input: {title!r}")
    done = completed_counts()
    print(f"Already completed: {dict(done)}")

    for temp in TEMPS:
        start = done.get(temp, 0)
        for i in range(start, RUNS_PER_TEMP):
            run_index = i + 1
            print(f"[temp {temp}] run {run_index}/{RUNS_PER_TEMP} ...", flush=True)
            try:
                res = run_pipeline_once(title, content, temp)
                append_row(run_index, temp, res["tags"], res["latency_ms"])
                print(f"   tags={res['tags']} latency={res['latency_ms']}ms", flush=True)
            except Exception as e:
                print(f"   ERROR on temp {temp} run {run_index}: {e}", flush=True)
                print("   Stopping. Re-run the script to resume from here.", flush=True)
                compute_metrics()
                return

    print("\nAll 40 runs complete.")
    compute_metrics()


if __name__ == "__main__":
    main()
