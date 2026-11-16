"""HW10 Part 3: freeze 20 Writer drafts, then validate the GEval judge against human labels.

  cases   run 20 questions through the HW8 agents and freeze the Writer drafts
          -> reports/hw10/cases/eval_cases.json + human_labels.csv (label column empty)
  show    print the 20 drafts to label by hand (1-5)
  label   interactive: one draft at a time, type 1-5, saves human_labels.csv
  check   confirm 20 labels 1-5 and that both files are committed and unchanged
  judge   (after check) run the judge 3 times on the 20 drafts, save raw rows + statistics
  stats   recompute the statistics from the saved raw CSV

Run: python3 code/run_hw10_part3.py cases | show | check | judge | stats
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "evaluation"))

from runtime import CASES, RAW, RUN_BY, build_service, trial_ids  # noqa: E402

CASES_FILE = CASES / "eval_cases.json"
LABELS_FILE = CASES / "human_labels.csv"
RAW_CSV = RAW / "part3_judge_runs.csv"
SUMMARY = RAW / "part3_judge_summary.json"
RUNS = 3
CASE_TRIES = 3


def questions(ids: list[str]) -> list[str]:
    """Return 20 domain questions (+2 spares): trial facts, guidance, harder or vague ones."""
    a, b, c, d, e, f = (ids * 6)[:6]
    return [
        f"What is the current status of trial {a}?",
        f"Which sponsor runs trial {b}?",
        f"How many enrollment slots does trial {c} have?",
        f"Is trial {d} still recruiting, and who sponsors it?",
        f"Summarize trial {e} for a coordinator in two sentences.",
        f"Compare the status of trials {a} and {f}.",
        "What should a patient check before joining a recruiting Phase II clinical trial?",
        "What does a Terminated status mean for a clinical trial listing?",
        "How should a coordinator explain informed consent to a new participant?",
        "What is the difference between Phase I and Phase III trials?",
        "Which documents should a site keep for each enrolled participant?",
        "What does 'Active, not recruiting' mean on a trial listing?",
        "How can a coordinator tell if a listing's enrollment count is out of date?",
        "What is the status of trial NCT00000001?",
        "Who sponsors trial NCT99999999 and how many slots are left?",
        "trial?",
        "Can my diabetic grandmother join any trial tomorrow?",
        "List every recruiting breast cancer trial in California with phone numbers.",
        "Why might a sponsor suspend a trial?",
        "What should a coordinator do when a participant wants to withdraw?",
        # spares, used only if an earlier question fails or hits the cache
        "What is an inclusion criterion in a clinical trial?",
        "How often should a coordinator update a trial listing?",
    ]


def git(*args: str) -> str:
    """Return the stripped stdout of a read-only git command run at the repo root."""
    root = CASES.parents[2]
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=False).stdout.strip()


def make_cases() -> None:
    """Return nothing; generate and save the 20 frozen drafts (never overwrites)."""
    from evaluator import collect

    if CASES_FILE.exists():
        raise SystemExit(f"{CASES_FILE.name} already exists: cases are frozen, not regenerated")
    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    service, _, _ = build_service(store=False, timeout_s=150)
    cases = []
    for n, q in enumerate(questions(trial_ids(6)), 1):
        if len(cases) == 20:
            break
        try:
            r = service.answer(q)
        except Exception as exc:
            print(f"C{n:02d} failed ({type(exc).__name__}: {exc}) -> skipped: {q}")
            continue
        if r["is_cached"]:
            print(f"C{n:02d} cache hit -> skipped (need a Writer draft): {q}")
            continue
        msgs = collect(r["trace_id"], r["started_ms"])
        if "draft" not in msgs:
            print(f"C{n:02d} no draft found for {r['trace_id']}")
            continue
        d = msgs["draft"]
        case = {"case_id": f"C{len(cases) + 1:02d}", "trace_id": r["trace_id"],
                "question": q, "facts": d.get("facts", ""), "plan": d.get("plan", []),
                "draft": d["draft"], "source": msgs["sources"]["draft"]}
        cases.append(case)
        print(f"{case['case_id']} {r['trace_id']} {len(d['draft'].split())} words  {q}")
    if len(cases) != 20:
        raise SystemExit(f"only {len(cases)} drafts collected; fix and re-run")
    CASES.mkdir(parents=True, exist_ok=True)
    CASES_FILE.write_text(json.dumps(cases, indent=2) + "\n")
    with open(LABELS_FILE, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "human_label"])
        w.writerows([c["case_id"], ""] for c in cases)
    print(f"Saved {CASES_FILE.name} (20 drafts) and {LABELS_FILE.name} (labels empty)")


def load_cases() -> list[dict]:
    """Return the frozen cases."""
    if not CASES_FILE.exists():
        raise SystemExit("run 'cases' first")
    return json.loads(CASES_FILE.read_text())


def load_labels() -> dict[str, int]:
    """Return {case_id: label}; exits if a label is missing or not an integer 1-5."""
    with open(LABELS_FILE, newline="") as fh:
        rows = list(csv.DictReader(fh))
    labels, bad = {}, []
    for r in rows:
        v = (r.get("human_label") or "").strip()
        if v not in {"1", "2", "3", "4", "5"}:
            bad.append(r["case_id"])
        else:
            labels[r["case_id"]] = int(v)
    if bad or len(labels) != 20:
        raise SystemExit(f"labels must be 1-5 for all 20 cases; bad/missing: {bad}")
    return labels


def show() -> None:
    """Return nothing; print each case for hand labeling."""
    for c in load_cases():
        print(f"\n=== {c['case_id']}  {c['question']}")
        if c["facts"]:
            print(f"records: {c['facts']}")
        print(f"draft: {c['draft']}")
    print("\nScale: 1 very poor, 2 poor, 3 adequate, 4 good, 5 excellent (accurate + useful)")


def label() -> None:
    """Return nothing; ask the human for a 1-5 label per draft and save the CSV."""
    cases = load_cases()
    labels = {}
    print("Type your own label 1-5 for each draft (1 very poor ... 5 excellent). q = quit.")
    for n, c in enumerate(cases, 1):
        print(f"\n[{n}/20] {c['case_id']}  {c['question']}")
        if c["facts"]:
            print(f"records: {c['facts']}")
        print(f"draft: {c['draft']}")
        while True:
            v = input("your label 1-5: ").strip().lower()
            if v == "q":
                raise SystemExit("stopped; nothing saved")
            if v in {"1", "2", "3", "4", "5"}:
                labels[c["case_id"]] = v
                break
    with open(LABELS_FILE, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "human_label"])
        w.writerows([c["case_id"], labels[c["case_id"]]] for c in cases)
    print(f"\nSaved {LABELS_FILE.name}: {[int(labels[c['case_id']]) for c in cases]}")


def check() -> dict:
    """Return the commit evidence for both files; exits if labels or commits are not ready."""
    labels = load_labels()
    out = {}
    for f in (CASES_FILE, LABELS_FILE):
        rel = str(f.relative_to(CASES.parents[2]))
        commit = git("log", "-1", "--format=%h %ci", "--", rel)
        dirty = git("status", "--porcelain", "--", rel)
        if not commit or dirty:
            raise SystemExit(f"{rel} must be committed and unchanged before the judge runs")
        out[rel] = commit
        print(f"committed: {rel} @ {commit}")
    dist = {k: list(labels.values()).count(k) for k in range(1, 6)}
    print(f"labels: 20 / 20, distribution {dist}")
    return out


def stats(rows: list[dict]) -> dict:
    """Return Spearman, MAD (per run) and repeatability over the per-case raw rows."""
    from scipy.stats import spearmanr

    runs = [f"run{k}" for k in range(1, RUNS + 1) if any(f"run{k}" in r for r in rows)]
    out = {"n": len(rows), "runs": len(runs), "per_run": {}, "judge_errors": {}}
    for k in runs:
        ok = [r for r in rows if r.get(k) is not None]
        out["judge_errors"][k] = [r["case_id"] for r in rows if r.get(k) is None]
        human, judge = [r["human"] for r in ok], [r[k] for r in ok]
        rho, p = spearmanr(human, judge)
        out["per_run"][k] = {
            "n": len(ok), "spearman": None if rho != rho else round(float(rho), 3),
            "p_value": None if p != p else round(float(p), 4),
            "mad": round(sum(abs(h - j) for h, j in zip(human, judge, strict=True)) / len(ok), 3),
            "exact_agree": sum(h == j for h, j in zip(human, judge, strict=True))}
    full = [r for r in rows if all(r.get(k) is not None for k in runs)]
    spread = [max(r[k] for k in runs) - min(r[k] for k in runs) for r in full]
    pairs = [abs(r[a] - r[b]) for r in full for i, a in enumerate(runs) for b in runs[i + 1:]]
    out["repeatability"] = {
        "cases_scored_all_runs": len(full),
        "cases_changed": sum(s > 0 for s in spread),
        "pct_changed": round(100 * sum(s > 0 for s in spread) / max(len(full), 1), 1),
        "pair_changes": sum(x > 0 for x in pairs), "pairs": len(pairs),
        "mean_abs_change": round(sum(pairs) / max(len(pairs), 1), 3),
        "max_abs_change": max(pairs, default=0)}
    first = [r[runs[0]] for r in rows if r.get(runs[0]) is not None]
    out["judge_mean"] = round(statistics.mean(first), 2)
    out["human_mean"] = round(statistics.mean(r["human"] for r in rows), 2)
    return out


def print_stats(s: dict) -> None:
    """Return nothing; print the statistics table."""
    print(f"\n=== Judge vs human (n={s['n']}, 1-5 scale) ===")
    print(f"{'run':<6}{'n':>4}{'spearman':>10}{'p':>9}{'MAD':>8}{'exact':>8}")
    for k, v in s["per_run"].items():
        print(f"{k:<6}{v['n']:>4}{v['spearman']!s:>10}{v['p_value']!s:>9}{v['mad']:>8}"
              f"{v['exact_agree']:>5}/{v['n']}")
    errs = {k: v for k, v in s["judge_errors"].items() if v}
    print(f"Judge errors (excluded per run): {errs or 'none'}")
    r = s["repeatability"]
    n_all = r["cases_scored_all_runs"]
    print(f"Repeatability: {r['cases_changed']}/{n_all} cases changed ({r['pct_changed']}%), "
          f"{r['pair_changes']}/{r['pairs']} run pairs differ, mean |change| "
          f"{r['mean_abs_change']}, max |change| {r['max_abs_change']}")
    print(f"Mean score: human {s['human_mean']}  judge run1 {s['judge_mean']}")


def save_rows(rows: list[dict]) -> None:
    """Return nothing; write the per-case raw rows (blank = judge error) to the CSV."""
    RAW.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(RAW_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def judge() -> None:
    """Return nothing; run the judge RUNS times on the frozen drafts and save raw + summary."""
    from judge import LocalJudge, score, settings

    print(f"Run by: {RUN_BY} (s3209)   {datetime.now():%Y-%m-%d %H:%M:%S}")
    evidence = check()
    labels, cases = load_labels(), load_cases()
    print(f"Judge: {json.dumps(settings())}")
    jdg = LocalJudge()
    rows = [{"case_id": c["case_id"], "trace_id": c["trace_id"], "human": labels[c["case_id"]]}
            for c in cases]
    for k in range(1, RUNS + 1):
        print(f"\n--- run {k} ---")
        for c, row in zip(cases, rows, strict=True):
            q = c["question"] + (f"\nTrial records:\n{c['facts']}" if c["facts"] else "")
            for attempt in range(1, CASE_TRIES + 1):
                res = score("helpfulness", q, c["draft"], jdg)
                if res["score"] is not None:
                    break
                print(f"{c['case_id']} judge error (try {attempt}/{CASE_TRIES}): {res['error']}")
            row[f"run{k}"] = res["score"]
            row[f"reason{k}"] = res["reason"] if res["score"] is not None else res["error"]
            print(f"{c['case_id']} human={row['human']} judge={res['score']}  "
                  f"{str(row[f'reason{k}'])[:90]}")
        save_rows(rows)  # keep finished runs even if a later one is interrupted
    s = stats(rows)
    s.update(judge=settings(), committed=evidence, run_at=f"{datetime.now():%Y-%m-%d %H:%M:%S}")
    SUMMARY.write_text(json.dumps(s, indent=2) + "\n")
    print_stats(s)
    print(f"Saved {RAW_CSV.relative_to(CASES.parents[2])} and {SUMMARY.name}")


def recompute() -> None:
    """Return nothing; recompute and print the statistics from the raw CSV."""
    if not RAW_CSV.exists():
        raise SystemExit("no judge results yet: label the cases, commit, then run 'judge' first")
    with open(RAW_CSV, newline="") as fh:
        rows = [{k: (int(v) if v and (k == "human" or k.startswith("run")) else
                     (None if k.startswith("run") else v)) for k, v in r.items()}
                for r in csv.DictReader(fh)]
    print(f"Recomputed from {RAW_CSV.name} ({len(rows)} rows)")
    print(f"{'case':<6}{'human':>6}" + "".join(f"{'run' + str(k):>6}" for k in range(1, RUNS + 1)))
    for r in rows:
        print(f"{r['case_id']:<6}{r['human']:>6}" +
              "".join(f"{r.get(f'run{k}') if r.get(f'run{k}') is not None else 'err'!s:>6}"
                      for k in range(1, RUNS + 1)))
    print_stats(stats(rows))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["cases", "show", "label", "check", "judge", "stats"])
    cmd = p.parse_args().cmd
    {"cases": make_cases, "show": show, "label": label, "check": check, "judge": judge,
     "stats": recompute}[cmd]()
