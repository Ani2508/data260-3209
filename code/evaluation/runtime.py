"""HW10 shared setup for the Part 2-4 runners: paths, the QA service and trial ids."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)
CODE = Path(__file__).resolve().parents[1]
for sub in ("semantic_cache", "kafka_agents", "web_application", "cache", "tracing",
            "evaluation"):
    if str(CODE / sub) not in sys.path:
        sys.path.insert(0, str(CODE / sub))

REPORTS = CODE.parent / "reports" / "hw10"
RAW = REPORTS / "raw"
CASES = REPORTS / "cases"
RUN_BY = "Ani Taraiya"


def build_service(store: bool = False, timeout_s: int = 300):
    """Return (QAService, SemanticCache, Embedder) wired to Redis and the HW8 agents."""
    import redis

    from pipeline import AgentPipeline
    from qa_service import QAService
    from semantic_cache import Embedder, SemanticCache
    from trial_cache import REDIS_URL

    client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    client.ping()
    embedder = Embedder()
    cache = SemanticCache(client, embedder.dim)
    cache.ensure_index()
    service = QAService(cache, embedder, AgentPipeline(timeout_s=timeout_s), store=store)
    return service, cache, embedder


def trial_ids(limit: int = 12) -> list[str]:
    """Return up to `limit` NCT ids from s3209_rel, lowest id first."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    from sqlalchemy import text

    from database import engine

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT nct_id FROM trials ORDER BY id LIMIT :n"),
                            {"n": limit}).all()
    if not rows:
        raise SystemExit("no trials in s3209_rel.trials")
    return [r[0] for r in rows]
