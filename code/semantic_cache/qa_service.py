"""HW9 Part 2: domain Q&A ingress with the semantic cache in front of the HW8 agents.

hit  (similarity >= threshold): return the stored answer, is_cached=True
miss: look up trial facts, run the HW8 pipeline, store the answer, is_cached=False
Part 3.5: with check_version=True a hit whose trial rows changed is deleted and re-run.
"""
from __future__ import annotations

import time

from common import log
from semantic_cache import Embedder, SemanticCache
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

    def answer(self, question: str) -> dict:
        """Return the answer with is_cached, similarity, latency_ms and per-step timings."""
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be a non-empty string")
        t0 = time.perf_counter()
        vec = self.embedder.encode(question)
        t1 = time.perf_counter()
        best = self.cache.nearest(vec)
        t2 = time.perf_counter()
        sim = best["similarity"] if best else 0.0
        timings = {"embed_ms": ms(t0, t1), "search_ms": ms(t1, t2)}

        stale = None
        if best and sim >= self.cache.threshold and self.check_version:
            stale = self.stale_version(best)
            if stale:
                self.cache.delete(best["key"])
                log("CACHE", f"STALE sim={sim:.4f} stored={best['data_version']} "
                             f"current={stale} -> entry deleted")
        if best and sim >= self.cache.threshold and not stale:
            latency = ms(t0, time.perf_counter())
            log("CACHE", f"HIT   sim={sim:.4f} matched='{best['query']}' latency={latency} ms")
            return {"question": question, "answer": best["answer"], "is_cached": True,
                    "similarity": sim, "latency_ms": latency, "timings": timings,
                    "matched_query": best["query"], "data_version": best["data_version"],
                    "agent_status": best["review"], "stale_invalidated": False}

        log("CACHE", f"MISS  best_sim={sim:.4f} -> HW8 agent pipeline")
        facts = find_trial_facts(question)
        t3 = time.perf_counter()
        final = self.pipeline.ask(question, facts["facts"])
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
