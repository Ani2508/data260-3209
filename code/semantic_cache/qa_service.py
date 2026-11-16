"""HW9 Part 2: domain Q&A ingress with the semantic cache in front of the HW8 agents.

hit  (similarity >= threshold): return the stored answer, is_cached=True
miss: look up trial facts, run the HW8 pipeline, store the answer, is_cached=False
Part 3.5: with check_version=True a hit whose trial rows changed is deleted and re-run.
"""
from __future__ import annotations

import time
import uuid

from common import epoch_ms, log
from semantic_cache import Embedder, SemanticCache
from tracer import span, write_span
from trial_facts import current_version, find_trial_facts


def ms(start: float, end: float) -> float:
    """Return the time between two perf_counter readings in milliseconds."""
    return round((end - start) * 1000, 1)


class QAService:
    """Query handler: embed, search the cache, and fall back to the agent pipeline."""

    def __init__(self, cache: SemanticCache, embedder: Embedder, pipeline,
                 check_version: bool = False, store: bool = True) -> None:
        """Return nothing; keep the cache, embedder, pipeline and the two switches."""
        self.cache = cache
        self.embedder = embedder
        self.pipeline = pipeline
        self.check_version = check_version
        self.store = store

    def stale_version(self, entry: dict) -> str | None:
        """Return the current data version if the entry's trial rows changed, else None."""
        ids = [int(x) for x in str(entry.get("trial_ids", "")).split(",") if x]
        if not ids:
            return None
        current = current_version(ids)
        return current if current != entry["data_version"] else None

    def answer(self, question: str, trace_id: str | None = None,
               fail_stage: str | None = None) -> dict:
        """Return the answer with trace_id, is_cached, similarity, latency and step timings."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        tid = trace_id or str(uuid.uuid4())  # HW10: one id for cache, Kafka and evaluator
        start_ms = epoch_ms()
        try:
            out = self._answer(question, tid, fail_stage)
        except Exception as exc:
            write_span(tid, "request", start_ms, epoch_ms(), "error",
                       f"{type(exc).__name__}: {exc}", question=question[:120])
            raise
        route = "hit" if out["is_cached"] else "miss"
        write_span(tid, "request", start_ms, epoch_ms(), route=route,
                   question=question[:120], review=out["agent_status"])
        return {**out, "trace_id": tid, "started_ms": start_ms}

    def _answer(self, question: str, tid: str, fail_stage: str | None) -> dict:
        """Return the answer dict for one request (spans: cache_lookup, facts)."""
        t0 = time.perf_counter()
        with span(tid, "cache_lookup", threshold=self.cache.threshold) as attrs:
            vec = self.embedder.encode(question)
            t1 = time.perf_counter()
            best = self.cache.nearest(vec)
            t2 = time.perf_counter()
            sim = best["similarity"] if best else 0.0
            stale = None
            if best and sim >= self.cache.threshold and self.check_version:
                stale = self.stale_version(best)
                if stale:
                    self.cache.delete(best["key"])
                    log("CACHE", f"STALE sim={sim:.4f} stored={best['data_version']} "
                                 f"current={stale} -> entry deleted")
            hit = bool(best and sim >= self.cache.threshold and not stale)
            attrs.update(result="hit" if hit else "miss", similarity=sim,
                         matched_query=best["query"] if hit else "")
        timings = {"embed_ms": ms(t0, t1), "search_ms": ms(t1, t2)}
        if hit:
            latency = ms(t0, time.perf_counter())
            log("CACHE", f"HIT   sim={sim:.4f} matched='{best['query']}' latency={latency} ms")
            return {"question": question, "answer": best["answer"], "is_cached": True,
                    "similarity": sim, "latency_ms": latency, "timings": timings,
                    "matched_query": best["query"], "data_version": best["data_version"],
                    "agent_status": best["review"], "stale_invalidated": False}

        log("CACHE", f"MISS  best_sim={sim:.4f} -> HW8 agent pipeline")
        with span(tid, "facts"):
            facts = find_trial_facts(question)
        t3 = time.perf_counter()
        final = self.pipeline.ask(question, facts["facts"], trace_id=tid, fail_stage=fail_stage)
        t4 = time.perf_counter()
        if self.store:
            self.cache.store(question, vec, final.get("answer", ""), facts["data_version"],
                             facts["trial_ids"], final.get("status", ""))
        t5 = time.perf_counter()
        timings.update(db_ms=ms(t2, t3), agent_ms=ms(t3, t4), store_ms=ms(t4, t5))
        latency = ms(t0, t5)
        log("CACHE", f"{'STORE' if self.store else 'DONE '} review={final.get('status')} "
                     f"version={facts['data_version']} latency={latency} ms")
        return {"question": question, "answer": final.get("answer", ""), "is_cached": False,
                "similarity": sim, "latency_ms": latency, "timings": timings,
                "matched_query": best["query"] if best else "",
                "data_version": facts["data_version"], "agent_status": final.get("status"),
                "stale_invalidated": bool(stale)}
