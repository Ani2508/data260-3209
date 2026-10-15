"""HW6 Part 3 - what memory costs.

Runs the same 30-message conversation in a fresh session for each setting
(SHORT_TERM_N = 4 / 12 / 30, plus the compression policy), asks the 5 probes,
scores them with memory_probes.yaml, and writes raw data + the cost table.

Needs the FastAPI backend on PORT_BASE (8509), MongoDB and Ollama running.
Run:  python3 code/run_hw06_memory_cost.py            (all settings)
      python3 code/run_hw06_memory_cost.py --only n4  (one setting)
"""
import argparse
import csv
import json
import re
import statistics
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
HW = ROOT / "reports" / "hw06"
RAW = HW / "raw"
BASE = "http://localhost:8509"
RUNNER = "Ani Taraiya"

SETTINGS = {                       # name -> (SHORT_TERM_N, policy)
    "n4": (4, "none"),
    "n12": (12, "none"),
    "n30": (30, "none"),
    "compress": (12, "compress"),  # memory-saving policy applied to the N=12 window
}
LABELS = {"n4": "SHORT_TERM_N=4", "n12": "SHORT_TERM_N=12", "n30": "SHORT_TERM_N=30",
          "compress": "Compression policy (N=12 + compress)"}
PRICE_IN, PRICE_OUT = 1.0 / 1e6, 5.0 / 1e6     # $ per token
CONVERSATIONS = 10_000

TURN_FIELDS = ["setting", "phase", "turn", "prompt_tokens", "completion_tokens",
               "system_primer_tokens", "long_term_tokens", "short_term_tokens", "episodic_tokens",
               "current_message_tokens", "prompt_tokens_est", "aux_prompt_tokens",
               "aux_completion_tokens", "latency_ms", "model_latency_ms", "window_messages",
               "session_summary", "lifetime_summary", "episodes_retrieved"]


def log(msg=""):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(HW / "RUN_LOG.txt", "a") as f:
        f.write(line + "\n")


def score_reply(reply: str, probe: dict, abstain: list) -> tuple:
    text = reply.lower()
    met = 0
    for group in probe["criteria"]:
        if any(re.search(r"(?<![0-9a-z])" + re.escape(k.lower()) + r"(?!\d)", text) for k in group):
            met += 1
    total = len(probe["criteria"])
    if met == 0:
        return (2 if any(a in text for a in abstain) else 1), met, total
    return 1 + round(4 * met / total), met, total


def chat(user_id, session_id, message, n, policy):
    r = requests.post(f"{BASE}/api/chat", json={"user_id": user_id, "session_id": session_id,
                                                "message": message, "short_term_n": n,
                                                "policy": policy}, timeout=900)
    r.raise_for_status()
    return r.json()


def row_from(setting, phase, turn, body):
    u = body["usage"]
    row = {k: u.get(k) for k in TURN_FIELDS if k in u}
    row.update(setting=setting, phase=phase, turn=turn,
               session_summary=int(u["summary_created"]["session_summary"]),
               lifetime_summary=int(u["summary_created"]["lifetime_summary"]),
               episodes_retrieved=len(body["used"]["episodic_facts"]))
    return row


def run_setting(name, convo, probes, abstain, stamp):
    n, policy = SETTINGS[name]
    user_id = f"cost_{name}_{stamp}"
    session_id = f"{user_id}-s1"
    log(f"--- {LABELS[name]}  user_id={user_id}  policy={policy}")
    rows, scores = [], []
    for i, msg in enumerate(convo, 1):
        body = chat(user_id, session_id, msg, n, policy)
        row = row_from(name, "conversation", i, body)
        rows.append(row)
        log(f"  turn {i:02d}  prompt={row['prompt_tokens']:5d}  completion={row['completion_tokens']:4d}  "
            f"window={row['window_messages']:2d}  latency={row['latency_ms']:8.0f} ms")
    for j, p in enumerate(probes, 1):
        body = chat(user_id, session_id, p["question"], n, policy)
        rows.append(row_from(name, "probe", len(convo) + j, body))
        s, met, total = score_reply(body["reply"], p, abstain)
        scores.append({"setting": name, "probe": p["id"], "question": p["question"], "score": s,
                       "criteria_met": met, "criteria_total": total, "reply": body["reply"],
                       "episodic_facts": [e["fact"] for e in body["used"]["episodic_facts"]]})
        log(f"  {p['id']} score={s} ({met}/{total})  reply: {body['reply'][:110]!r}")
    return rows, scores


def summarize(rows, scores):
    out = {}
    for name in SETTINGS:
        conv = [r for r in rows if r["setting"] == name and r["phase"] == "conversation"]
        allr = [r for r in rows if r["setting"] == name]
        sc = [s["score"] for s in scores if s["setting"] == name]
        if not conv:
            continue
        p_in = sum(r["prompt_tokens"] + r["aux_prompt_tokens"] for r in conv)
        p_out = sum(r["completion_tokens"] + r["aux_completion_tokens"] for r in conv)
        reply_in = sum(r["prompt_tokens"] for r in conv)
        reply_out = sum(r["completion_tokens"] for r in conv)
        out[name] = {
            "label": LABELS[name],
            "mean_prompt_tokens_per_turn": round(statistics.mean(r["prompt_tokens"] for r in conv), 1),
            "mean_prompt_tokens_est_per_turn": round(statistics.mean(r["prompt_tokens_est"] for r in conv), 1),
            "mean_short_term_tokens": round(statistics.mean(r["short_term_tokens"] for r in conv), 1),
            "mean_long_term_tokens": round(statistics.mean(r["long_term_tokens"] for r in conv), 1),
            "mean_episodic_tokens": round(statistics.mean(r["episodic_tokens"] for r in conv), 1),
            "mean_completion_tokens": round(statistics.mean(r["completion_tokens"] for r in conv), 1),
            "mean_latency_ms": round(statistics.mean(r["latency_ms"] for r in conv), 1),
            "mean_model_latency_ms": round(statistics.mean(r["model_latency_ms"] for r in conv), 1),
            "probe_quality": round(statistics.mean(sc), 2) if sc else None,
            "probe_scores": sc,
            "tokens_per_conversation": {"reply_in": reply_in, "reply_out": reply_out,
                                        "all_calls_in": p_in, "all_calls_out": p_out},
            "cost_10k_reply_only_usd": round(CONVERSATIONS * (reply_in * PRICE_IN + reply_out * PRICE_OUT), 2),
            "cost_10k_all_calls_usd": round(CONVERSATIONS * (p_in * PRICE_IN + p_out * PRICE_OUT), 2),
            "probe_turn_mean_prompt_tokens": round(statistics.mean(
                r["prompt_tokens"] for r in allr if r["phase"] == "probe"), 1),
        }
    return out


def write_outputs(rows, scores, summary):
    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / "part3_turns.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TURN_FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(RAW / "part3_probe_scores.json", "w") as f:
        json.dump(scores, f, indent=2)
    with open(RAW / "part3_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    if "n12" in summary and "compress" in summary:
        a, b = summary["n12"], summary["compress"]
        comp = {
            "baseline": "SHORT_TERM_N=12, no policy",
            "policy": "compress: keep newest 4 messages verbatim, older assistant replies -> first "
                      "sentence (<=120 chars), older user messages -> 200 chars, evict oldest until "
                      "window <= 500 est. tokens",
            "baseline_mean_prompt_tokens": a["mean_prompt_tokens_per_turn"],
            "policy_mean_prompt_tokens": b["mean_prompt_tokens_per_turn"],
            "token_saving_pct": round(100 * (1 - b["mean_prompt_tokens_per_turn"] / a["mean_prompt_tokens_per_turn"]), 1),
            "baseline_short_term_tokens": a["mean_short_term_tokens"],
            "policy_short_term_tokens": b["mean_short_term_tokens"],
            "baseline_probe_quality": a["probe_quality"],
            "policy_probe_quality": b["probe_quality"],
            "baseline_latency_ms": a["mean_latency_ms"],
            "policy_latency_ms": b["mean_latency_ms"],
        }
        with open(RAW / "part3_compression_comparison.json", "w") as f:
            json.dump(comp, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=list(SETTINGS), nargs="*")
    args = ap.parse_args()
    convo = yaml.safe_load(open(HW / "cases" / "conversation_30.yaml"))["messages"]
    pdoc = yaml.safe_load(open(HW / "memory_probes.yaml"))
    probes, abstain = pdoc["probes"], pdoc["abstain_keywords"]
    assert len(convo) == 30 and len(probes) == 5

    stamp = datetime.now().strftime("%m%d%H%M")
    log("=" * 78)
    log(f"RUN: python3 code/run_hw06_memory_cost.py   (HW6 Part 3)   run by: {RUNNER}")
    log(f"backend {BASE}  conversation=30 msgs  probes=5  stamp={stamp}")
    rows, scores = [], []
    prev = RAW / "part3_turns.csv"
    if args.only and prev.exists():          # keep results of settings not re-run
        keep = set(SETTINGS) - set(args.only)
        with open(prev) as f:
            for r in csv.DictReader(f):
                if r["setting"] in keep:
                    rows.append({k: (r[k] if k in ("setting", "phase") else float(r[k])) for k in TURN_FIELDS})
        old = json.load(open(RAW / "part3_probe_scores.json"))
        scores = [s for s in old if s["setting"] in keep]
    t0 = time.time()
    for name in (args.only or list(SETTINGS)):
        r, s = run_setting(name, convo, probes, abstain, stamp)
        rows += r
        scores += s
        write_outputs(rows, scores, summarize(rows, scores))   # save after each setting
    summary = summarize(rows, scores)
    write_outputs(rows, scores, summary)

    log("-" * 78)
    log(f"{'Setting':40s} {'Prompt tok/turn':>15s} {'Latency ms':>11s} {'Probe (1-5)':>11s}")
    for name, s in summary.items():
        log(f"{s['label']:40s} {s['mean_prompt_tokens_per_turn']:15.1f} {s['mean_latency_ms']:11.1f} "
            f"{s['probe_quality']:11.2f}")
    log("-" * 78)
    log("Cost of 10,000 x 30-turn conversations ($1/M input, $5/M output)")
    for name, s in summary.items():
        log(f"{s['label']:40s} reply-only ${s['cost_10k_reply_only_usd']:9.2f}   "
            f"all calls ${s['cost_10k_all_calls_usd']:9.2f}")
    log(f"total wall time {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
