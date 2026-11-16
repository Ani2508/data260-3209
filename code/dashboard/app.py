"""HW10 Part 1: s3209 operations dashboard (Summary, Evaluation, Trace lookup).

Reads the HW10 evidence files (spans, evaluation, judge validation) and, when Redis is up,
the live semantic-cache size. Run: streamlit run code/dashboard/app.py --server.port 8510
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE / "tracing"))
from tracer import STAGE_ORDER, journey, load_spans  # noqa: E402

RAW = CODE.parent / "reports" / "hw10" / "raw"
SPANS = RAW / "spans.jsonl"
EVALS = RAW / "eval_results.jsonl"
JUDGE_SUMMARY = RAW / "part3_judge_summary.json"
JUDGE_RUNS = RAW / "part3_judge_runs.csv"
TRACES = RAW / "traces.json"
LATENCY = RAW / "part4_latency_summary.json"
COLORS = {"miss": "#2a78d6", "hit": "#eb6834"}  # categorical slots 1-2, validated pair
WINDOWS = {"Last 1 hour": 3600, "Last 24 hours": 86400, "Last 7 days": 7 * 86400,
           "All data": None}

st.set_page_config(page_title="s3209 operations", layout="wide")


@st.cache_resource
def redis_client():
    """Return one shared Redis client (reused across reruns), or None if Redis is down."""
    try:
        import redis

        sys.path.insert(0, str(CODE / "cache"))
        from trial_cache import REDIS_URL

        client = redis.Redis.from_url(REDIS_URL, decode_responses=True, socket_timeout=1)
        client.ping()
        return client
    except Exception:
        return None


@st.cache_data(ttl=15)
def spans_df(mtime: float) -> pd.DataFrame:
    """Return all spans as a DataFrame (cache key includes the file mtime)."""
    rows = load_spans(SPANS)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["route"] = df["attrs"].map(lambda a: a.get("route") or a.get("result"))
    return df


@st.cache_data(ttl=15)
def read_jsonl(path: str, mtime: float) -> list[dict]:
    """Return the JSON objects in a .jsonl file, skipping malformed lines."""
    out = []
    p = Path(path)
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def mtime(p: Path) -> float:
    """Return the file's modification time (0 when it does not exist)."""
    return p.stat().st_mtime if p.exists() else 0.0


def read_json(p: Path):
    """Return parsed JSON from p, or None if the file is missing."""
    return json.loads(p.read_text()) if p.exists() else None


def source(text: str) -> None:
    """Return nothing; print the data-source caption under a metric block."""
    st.caption(f"Source: {text}")


# ---------------------------------------------------------------- Summary
def page_summary() -> None:
    """Return nothing; render request count, hit rate, error rate and latency."""
    st.header("Summary")
    window = st.selectbox("Time window", list(WINDOWS), index=3)
    df = spans_df(mtime(SPANS))
    if df.empty:
        st.info("No spans yet: run the HW10 commands first.")
        return
    req = df[df["stage"] == "request"].copy()
    secs = WINDOWS[window]
    if secs:
        req = req[req["start_ms"] >= time.time() * 1000 - secs * 1000]
    span_txt = (f"{pd.to_datetime(req['start_ms'].min(), unit='ms'):%Y-%m-%d %H:%M} to "
                f"{pd.to_datetime(req['start_ms'].max(), unit='ms'):%Y-%m-%d %H:%M} UTC"
                if len(req) else "no requests")
    st.markdown(f"**Window:** {window} ({span_txt})")
    if req.empty:
        st.warning("No requests in this window.")
        return
    hits = req[req["route"] == "hit"]
    misses = req[req["route"] == "miss"]
    errors = req[req["status"] == "error"]
    ok_miss = misses[misses["status"] == "ok"]

    c = st.columns(4)
    c[0].metric("Requests", len(req))
    c[1].metric("Cache hits", len(hits))
    c[2].metric("Cache misses", len(req) - len(hits),
                help="misses that completed + failed requests (failures never hit)")
    c[3].metric("Hit rate", f"{100 * len(hits) / len(req):.1f}%")
    source(f"`request` spans in {SPANS.name} (route=hit/miss from the cache_lookup span), "
           f"{window.lower()}")

    c = st.columns(4)
    c[0].metric("Error rate", f"{100 * len(errors) / len(req):.1f}%", help=f"{len(errors)} errors")
    c[1].metric("Miss p50 / p95", f"{ok_miss['duration_ms'].median():.0f} / "
                f"{ok_miss['duration_ms'].quantile(.95):.0f} ms" if len(ok_miss) else "–")
    c[2].metric("Hit p50 / p95", f"{hits['duration_ms'].median():.0f} / "
                f"{hits['duration_ms'].quantile(.95):.0f} ms" if len(hits) else "–")
    ev = df[df["stage"] == "evaluator"]
    c[3].metric("Evaluator spans", len(ev))
    source("`request` span duration = cache lookup -> final answer (user-facing end-to-end); "
           "error rate = request spans with status=error")

    r = redis_client()
    if r is not None:
        try:
            n = r.ft("s3209_semcache_idx").info().get("num_docs", "?")
            st.caption(f"Live: Redis s3209_semcache_idx holds {n} cached answers "
                       "(shared client via st.cache_resource)")
        except Exception:
            st.caption("Live: Redis up, cache index not found")
    else:
        st.caption("Live: Redis not reachable (summary uses span logs only)")

    st.subheader("End-to-end latency by route")
    plot = req[req["status"] == "ok"][["start_ms", "duration_ms", "route", "trace_id"]].copy()
    plot["time"] = pd.to_datetime(plot["start_ms"], unit="ms")
    chart = alt.Chart(plot).mark_circle(size=70, opacity=0.85).encode(
        x=alt.X("time:T", title="request start (UTC)"),
        y=alt.Y("duration_ms:Q", title="latency (ms, log)", scale=alt.Scale(type="log")),
        color=alt.Color("route:N", title="route",
                        scale=alt.Scale(domain=list(COLORS), range=list(COLORS.values()))),
        tooltip=["trace_id", "route", alt.Tooltip("duration_ms:Q", format=".1f")])
    st.altair_chart(chart, width="stretch")
    with st.expander("Table view"):
        st.dataframe(req[["trace_id", "route", "status", "duration_ms", "start", "error"]],
                     hide_index=True, width="stretch")


# ---------------------------------------------------------------- Evaluation
def page_evaluation() -> None:
    """Return nothing; render Part 2 scores and Part 3 judge validation."""
    st.header("Evaluation")
    evals = [e for e in read_jsonl(str(EVALS), mtime(EVALS))
             if e.get("status") == "ok" and e.get("scores")]  # judge errors are excluded
    st.subheader("Pipeline scores by case (GEval, 1-5)")
    if not evals:
        st.info("No evaluation results yet (make hw10-part2).")
    else:
        rows = [{"trace_id": e["trace_id"][:8], "question": e["question"][:48],
                 "Planner (plan)": e["scores"]["plan_quality"]["score"],
                 "Writer (draft)": e["scores"]["writer_helpfulness"]["score"],
                 "Reviewer (final)": e["scores"]["final_helpfulness"]["score"],
                 "final - draft": e["scores"]["improvement"]["diff"],
                 "review": e.get("review_status"),
                 "same text": e["scores"]["improvement"]["same_text"]} for e in evals]
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, width="stretch")
        source(f"{EVALS.name} ({len(df)} evaluated traces); judge "
               f"{evals[-1]['judge']['model']}, temperature {evals[-1]['judge']['temperature']}")
        means = df[["Planner (plan)", "Writer (draft)", "Reviewer (final)"]].mean()
        bars = pd.DataFrame({"stage": means.index, "mean score": means.values})
        st.altair_chart(alt.Chart(bars).mark_bar(color=COLORS["miss"], cornerRadiusEnd=4,
                                                 size=36).encode(
            x=alt.X("stage:N", sort=None, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("mean score:Q", scale=alt.Scale(domain=[0, 5]), title="mean score (1-5)"),
            tooltip=["stage", alt.Tooltip("mean score:Q", format=".2f")]),
            width="stretch")
        same = df["same text"].mean() * 100
        improved = (df["final - draft"] > 0).mean() * 100
        st.markdown("**Interpretation**")
        st.markdown(
            f"- Planner plans average **{means.iloc[0]:.2f}/5**; Writer drafts "
            f"**{means.iloc[1]:.2f}/5**; final answers **{means.iloc[2]:.2f}/5**.\n"
            f"- Final text equals the draft in **{same:.0f}%** of traces: the Reviewer "
            f"approves or rejects but does not rewrite, so it adds a gate, not quality.\n"
            f"- Final scored higher than the draft in **{improved:.0f}%** of traces; "
            f"any difference on identical text is judge noise, not improvement.\n"
            f"- Coordination works as a hand-off (same correlation_id end to end), but quality "
            f"is set by the Planner + Writer; a revising Reviewer would be needed to improve it.")

    st.subheader("Judge validation (20 frozen drafts vs human labels)")
    s = read_json(JUDGE_SUMMARY)
    if not s:
        st.info("No judge validation yet (make hw10-part3-judge).")
        return
    run1 = s["per_run"]["run1"]
    rep = s["repeatability"]
    c = st.columns(4)
    c[0].metric("Spearman (run 1)", run1["spearman"], help=f"p = {run1['p_value']}")
    c[1].metric("Mean abs diff", run1["mad"])
    scored = rep.get("cases_scored_all_runs", s["n"])
    c[2].metric("Cases changed (3 runs)", f"{rep['cases_changed']}/{scored}")
    c[3].metric("Max |change|", rep["max_abs_change"], help=f"mean {rep['mean_abs_change']}")
    st.dataframe(pd.DataFrame([{"run": k, **v} for k, v in s["per_run"].items()]),
                 hide_index=True, width="stretch")
    source(f"{JUDGE_SUMMARY.name}; judge {s['judge']['model']}, temperature "
           f"{s['judge']['temperature']}, seed {s['judge']['seed']}; files committed "
           f"{', '.join(s['committed'].values())}")
    if JUDGE_RUNS.exists():
        with open(JUDGE_RUNS, newline="") as fh:
            raw = pd.DataFrame(list(csv.DictReader(fh)))
        st.markdown("**Raw per-case scores** (recompute: `make hw10-part3-stats`)")
        cols = [c for c in raw.columns if not c.startswith("reason")]
        st.dataframe(raw[cols], hide_index=True, width="stretch", height=36 * (len(raw) + 1) + 4)
        errs = sorted({c for v in s.get("judge_errors", {}).values() for c in v})
        if errs:
            st.caption(f"Blank = judge error on every retry (excluded): {', '.join(errs)}")


# ---------------------------------------------------------------- Trace lookup
def page_trace() -> None:
    """Return nothing; render one trace's journey from its trace_id."""
    st.header("Trace lookup")
    examples = read_json(TRACES) or {}
    if examples:
        cols = st.columns(len(examples))
        for col, (kind, info) in zip(cols, examples.items(), strict=True):
            if col.button(f"{kind} example", width="stretch"):
                st.session_state["tid"] = info["trace_id"]
    tid = st.text_input("trace_id", key="tid").strip()
    if not tid:
        saved = ", ".join(f"{k}={v['trace_id']}" for k, v in examples.items())
        st.caption(f"Saved examples: {saved}" if examples else "Paste a trace_id")
        return
    spans = journey(load_spans(SPANS, trace_id=tid))
    if not spans:
        st.error(f"No spans for {tid}")
        return
    lookup = next((s for s in spans if s["stage"] == "cache_lookup"), None)
    route = (lookup or {}).get("attrs", {}).get("result", "unknown")
    failed = [s for s in spans if s["status"] == "error"]
    req = next((s for s in spans if s["stage"] == "request"), None)
    c = st.columns(4)
    c[0].metric("Path", f"CACHE {route.upper()}")
    c[1].metric("Spans", len(spans))
    c[2].metric("Status", "ERROR" if failed else "OK")
    c[3].metric("Request ms", f"{req['duration_ms']:.0f}" if req else "–")
    if route == "hit":
        st.success(f"Cache HIT: served from Redis (similarity {lookup['attrs']['similarity']}); "
                   "no Kafka or agent stages.")
    elif route == "miss" and not failed:
        st.info("Cache MISS: cache_lookup -> inbox -> Planner -> tasks -> Writer -> drafts -> "
                "Reviewer -> final -> evaluator.")
    elif route == "miss":
        stages = " -> ".join(dict.fromkeys(s["stage"] for s in spans if s["stage"] != "request"))
        st.warning(f"Cache MISS path stopped early: {stages}")
    if failed:
        first = next(s for s in spans if s["status"] == "error" and s["stage"] != "request")
        st.error(f"Failed at **{first['stage']}**: {first['error']}")
    table = pd.DataFrame([{"#": i, "stage": s["stage"], "start": s["start"][11:23],
                           "end": s["end"][11:23], "duration ms": s["duration_ms"],
                           "status": "✓ ok" if s["status"] == "ok" else "✗ error",
                           "error": s["error"] or "",
                           "detail": ", ".join(f"{k}={v}" for k, v in s["attrs"].items()
                                               if k not in ("question", "matched_query"))}
                          for i, s in enumerate(spans, 1)])
    st.dataframe(table, hide_index=True, width="stretch", height=36 * (len(table) + 1) + 4)
    t0 = spans[0]["start_ms"]
    g = pd.DataFrame([{"stage": s["stage"], "from": s["start_ms"] - t0, "to": s["end_ms"] - t0,
                       "status": s["status"], "ms": s["duration_ms"]} for s in spans
                      if s["stage"] != "request"])
    if not g.empty:
        span_ms = max(g["to"].max(), 1.0)
        g["to"] = g[["from", "to"]].max(axis=1).clip(lower=g["from"] + span_ms * 0.004)
        st.altair_chart(alt.Chart(g).mark_bar(size=14, cornerRadius=3).encode(
            y=alt.Y("stage:N", sort=[s for s in STAGE_ORDER], title=None),
            x=alt.X("from:Q", title="ms since request start"), x2="to:Q",
            color=alt.Color("status:N", scale=alt.Scale(domain=["ok", "error"],
                                                        range=["#2a78d6", "#d03b3b"])),
            tooltip=["stage", "status", alt.Tooltip("ms:Q", format=".1f")]),
            width="stretch")
    source(f"{SPANS.name}, all spans with trace_id = {tid}")


def page_latency() -> None:
    """Return nothing; render the Part 4 stage-latency table."""
    st.header("Stage latency (50 cache misses)")
    s = read_json(LATENCY)
    if not s:
        st.info("No latency run yet (make hw10-part4-latency).")
        return
    names = {"cache_lookup": "Cache lookup", "planner": "Planner", "writer": "Writer",
             "reviewer": "Reviewer", "queue_wait": "Queue wait (total)",
             "evaluator": "Evaluation", "facts": "Facts (MySQL)", "e2e_ms": "End-to-end"}
    st.dataframe(pd.DataFrame([{"stage": n, "p50 ms": s["table"][k]["p50"],
                                "p95 ms": s["table"][k]["p95"],
                                "% of e2e": s["table"][k]["pct_of_e2e"]}
                               for k, n in names.items()]),
                 hide_index=True, width="stretch")
    h = s["cache_hit_latency"]
    c = st.columns(3)
    c[0].metric("Dominant stage", names[s["dominant"]])
    c[1].metric("Cache-hit p50", f"{h['p50']} ms" if h["p50"] is not None else "–")
    c[2].metric("Cache-hit p95", f"{h['p95']} ms" if h["p95"] is not None else "–")
    source(f"{LATENCY.name}: {s['n']} confirmed cache misses; e2e = {s['e2e_definition']}; "
           "cache-hit latency from request spans with route=hit (kept separate)")


pages = {"Summary": page_summary, "Evaluation": page_evaluation,
         "Trace lookup": page_trace, "Latency": page_latency}
st.sidebar.title("s3209 operations")
choice = st.sidebar.radio("Page", list(pages))
st.sidebar.caption("Ani Taraiya · DATA 260 HW10 · PREFIX s3209")
pages[choice]()
