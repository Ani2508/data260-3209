"""Short-term, long-term (summaries) and episodic memory for /api/chat (HW6 Parts 2-3).

Every model call goes through the HW1 adapter (src/model_client.py).
"""
import hashlib
import json
import math
import re
import sys
import time
from datetime import datetime, timezone

import requests

import config

sys.path.insert(0, str(config.ROOT / "src"))
from model_client import ModelClient  # noqa: E402

SYSTEM_PRIMER = (
    "You are TrialMate, an assistant for a clinical trial coordinator. "
    "Answer in at most 4 short sentences. Use the remembered context below when it is relevant. "
    "If a detail was never mentioned, say you do not know instead of guessing."
)

_clients = {}


def _client(kind: str) -> ModelClient:
    """One adapter instance per call type (reply text, JSON extraction, summaries)."""
    if kind not in _clients:
        common = dict(model=config.CHAT_MODEL, base_url=config.OLLAMA_URL, temperature=0.0,
                      num_ctx=config.NUM_CTX, seed=config.SEED)
        if kind == "reply":
            _clients[kind] = ModelClient(force_json=False, num_predict=config.MAX_REPLY_TOKENS, **common)
        elif kind == "json":
            _clients[kind] = ModelClient(force_json=True, num_predict=300, **common)
        else:
            _clients[kind] = ModelClient(force_json=False, num_predict=300, **common)
    return _clients[kind]


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------------ token accounting
def est_tokens(text: str) -> int:
    """Section-level token estimate (~4 characters per token)."""
    return math.ceil(len(text) / 4) if text else 0


# ------------------------------------------------------------------ embeddings + retrieval
_embed_backend = {"name": None}


def _hash_embed(text: str, dim: int = 256) -> list:
    """Fallback only (embed model unavailable): hashed bag of words."""
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) % 2 else -1.0
    return vec


def embed(texts: list) -> list:
    if not texts:
        return []
    try:
        r = requests.post(f"{config.OLLAMA_URL}/api/embed",
                          json={"model": config.EMBED_MODEL, "input": texts}, timeout=60)
        r.raise_for_status()
        _embed_backend["name"] = config.EMBED_MODEL
        return [[float(x) for x in v] for v in r.json()["embeddings"]]
    except Exception:
        _embed_backend["name"] = "hash-256 (fallback)"
        return [_hash_embed(t) for t in texts]


def cosine(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve_episodes(db, user_id: str, query_vec: list, k: int = config.EPISODES_TOP_K) -> list:
    """Top-k stored facts for this user by cosine similarity to the current message."""
    scored = []
    for ep in db.episodes.find({"user_id": user_id}, {"fact": 1, "importance": 1, "embedding": 1}):
        scored.append({"fact": ep["fact"], "importance": ep["importance"],
                       "score": round(cosine(query_vec, ep["embedding"]), 4)})
    scored.sort(key=lambda e: e["score"], reverse=True)
    return scored[:k]


# ------------------------------------------------------------------ episodic extraction
EXTRACT_PROMPT = (
    "Extract up to 3 short, durable facts about the user or their clinical trial from the message "
    "(names, IDs, numbers, dates, places, preferences, decisions). Ignore questions and small talk. "
    'Return JSON only: {"facts": [{"fact": "<max 20 words>", "importance": <0..1>}]}. '
    'Return {"facts": []} if there is nothing worth remembering.'
)


def extract_episodes(message: str, aux=None) -> list:
    res = _client("json").complete([{"role": "system", "content": EXTRACT_PROMPT},
                                    {"role": "user", "content": message}])
    _add_aux(aux, res)
    try:
        facts = json.loads(res.text).get("facts", [])
    except (json.JSONDecodeError, AttributeError):
        return []
    out = []
    for f in facts[:config.MAX_FACTS_PER_MESSAGE]:
        if isinstance(f, dict) and str(f.get("fact", "")).strip():
            imp = f.get("importance", 0.5)
            imp = min(1.0, max(0.0, float(imp))) if isinstance(imp, (int, float)) else 0.5
            out.append({"fact": str(f["fact"]).strip()[:300], "importance": imp})
    return out


def store_episodes(db, user_id: str, session_id: str, facts: list) -> list:
    """Embed each fact and store it; skip near-duplicates (cosine >= 0.95)."""
    if not facts:
        return []
    vecs = embed([f["fact"] for f in facts])
    existing = [e["embedding"] for e in db.episodes.find({"user_id": user_id}, {"embedding": 1})]
    saved = []
    for f, v in zip(facts, vecs):
        if any(cosine(v, e) >= 0.95 for e in existing):
            continue
        db.episodes.insert_one({"user_id": user_id, "session_id": session_id, "fact": f["fact"],
                                "importance": float(f["importance"]), "embedding": v,
                                "created_at": now()})
        existing.append(v)
        saved.append(f)
    return saved


# ------------------------------------------------------------------ short-term window + policy
def load_window(db, user_id: str, session_id: str, n: int, exclude_id=None) -> list:
    """Sliding window: last n messages of this session (oldest first)."""
    if n <= 0:
        return []
    q = {"user_id": user_id, "session_id": session_id}
    if exclude_id is not None:
        q["_id"] = {"$ne": exclude_id}
    docs = list(db.messages.find(q).sort([("created_at", -1), ("_id", -1)]).limit(n))
    return [{"role": d["role"], "content": d["content"]} for d in reversed(docs)]


def _first_sentence(text: str, limit: int = 120) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip(), flags=re.S)
    s = (m.group(1) if m else text.strip())
    return s if len(s) <= limit else s[:limit].rstrip() + "..."


def apply_policy(window: list, policy: str, keep_recent: int = 4, budget: int = 500) -> list:
    """Compression policy (Part 3.4).

    'compress': the newest `keep_recent` messages stay verbatim; older assistant replies
    are cut to their first sentence (<=120 chars) and older user messages to 200 chars;
    then the oldest messages are evicted until the window fits `budget` estimated tokens.
    """
    if policy != "compress" or not window:
        return window
    cut = max(0, len(window) - keep_recent)
    out = []
    for i, m in enumerate(window):
        c = m["content"]
        if i < cut:
            c = _first_sentence(c) if m["role"] == "assistant" else (c[:200] + ("..." if len(c) > 200 else ""))
        out.append({"role": m["role"], "content": c})
    while len(out) > keep_recent and sum(est_tokens(m["content"]) for m in out) > budget:
        out.pop(0)
    return out


# ------------------------------------------------------------------ summaries
def latest_summary(db, user_id: str, scope: str, session_id=None):
    q = {"user_id": user_id, "scope": scope}
    if scope == "session":
        q["session_id"] = session_id
    doc = db.summaries.find_one(q, sort=[("created_at", -1), ("_id", -1)])
    return doc["text"] if doc else None


SUMMARY_PROMPT = (
    "Update the running summary of this conversation. Write at most 6 concise bullets "
    "('- ' prefix) keeping every concrete fact (names, IDs, numbers, dates, places, decisions). "
    "No intro text."
)
LIFETIME_PROMPT = (
    "Condense these session summaries into one lifetime profile of the user: at most 8 bullets "
    "('- ' prefix), keep concrete facts, drop duplicates, newer facts win. No intro text."
)


def _add_aux(aux, res):
    """Accumulate tokens of helper calls (extraction, summaries) for cost accounting."""
    if aux is not None:
        aux["aux_prompt_tokens"] += res.input_tokens
        aux["aux_completion_tokens"] += res.output_tokens


def maybe_summarize(db, user_id: str, session_id: str, aux=None) -> dict:
    """Every SUMMARIZE_EVERY_USER_MSGS user messages -> new session summary;
    every LIFETIME_EVERY_SESSION_SUMMARIES session summaries -> refresh lifetime summary."""
    info = {"session_summary": False, "lifetime_summary": False}
    m = config.SUMMARIZE_EVERY_USER_MSGS
    n_user = db.messages.count_documents({"user_id": user_id, "session_id": session_id, "role": "user"})
    if n_user == 0 or n_user % m:
        return info
    recent = load_window(db, user_id, session_id, 2 * m)
    prev = latest_summary(db, user_id, "session", session_id) or "(none)"
    convo = "\n".join(f"{x['role']}: {x['content']}" for x in recent)
    res = _client("text").complete([
        {"role": "system", "content": SUMMARY_PROMPT},
        {"role": "user", "content": f"Previous summary:\n{prev}\n\nRecent messages:\n{convo}"}])
    _add_aux(aux, res)
    db.summaries.insert_one({"user_id": user_id, "session_id": session_id, "scope": "session",
                             "text": res.text.strip(), "created_at": now()})
    info["session_summary"] = True

    n_sess = db.summaries.count_documents({"user_id": user_id, "scope": "session"})
    if n_sess % config.LIFETIME_EVERY_SESSION_SUMMARIES == 0:
        sess = list(db.summaries.find({"user_id": user_id, "scope": "session"})
                    .sort("created_at", -1).limit(5))
        prev_life = latest_summary(db, user_id, "user") or "(none)"
        joined = "\n\n".join(s["text"] for s in reversed(sess))
        res = _client("text").complete([
            {"role": "system", "content": LIFETIME_PROMPT},
            {"role": "user", "content": f"Current lifetime summary:\n{prev_life}\n\nSession summaries:\n{joined}"}])
        _add_aux(aux, res)
        db.summaries.insert_one({"user_id": user_id, "session_id": None, "scope": "user",
                                 "text": res.text.strip(), "created_at": now()})
        info["lifetime_summary"] = True
    return info


# ------------------------------------------------------------------ prompt assembly
def build_prompt(session_summary, lifetime_summary, episodes, window, message):
    """system primer + long-term summaries + episodic facts (system message),
    then the short-term window, then the current user message."""
    long_term = ""
    if lifetime_summary:
        long_term += f"\n\nLifetime summary of this user:\n{lifetime_summary}"
    if session_summary:
        long_term += f"\n\nSummary of this session so far:\n{session_summary}"
    facts = ""
    if episodes:
        facts = "\n\nRemembered facts (most relevant first):\n" + "\n".join(f"- {e['fact']}" for e in episodes)
    messages = [{"role": "system", "content": SYSTEM_PRIMER + long_term + facts}]
    messages += window
    messages.append({"role": "user", "content": message})
    sections = {
        "system_primer_tokens": est_tokens(SYSTEM_PRIMER),
        "long_term_tokens": est_tokens(long_term),
        "episodic_tokens": est_tokens(facts),
        "short_term_tokens": sum(est_tokens(m["content"]) for m in window),
        "current_message_tokens": est_tokens(message),
    }
    return messages, sections


# ------------------------------------------------------------------ one chat turn
def chat_turn(db, user_id: str, session_id: str, message: str, short_term_n=None, policy=None) -> dict:
    t0 = time.perf_counter()
    n = config.SHORT_TERM_N if short_term_n is None else short_term_n
    policy = policy or config.MEMORY_POLICY

    # 1. save the user message
    uid = db.messages.insert_one({"user_id": user_id, "session_id": session_id, "role": "user",
                                  "content": message, "created_at": now()}).inserted_id
    # 2. short-term window (+ optional compression policy)
    raw_window = load_window(db, user_id, session_id, n, exclude_id=uid)
    window = apply_policy(raw_window, policy)
    # 3. long-term summaries
    sess_sum = latest_summary(db, user_id, "session", session_id)
    life_sum = latest_summary(db, user_id, "user")
    # 4. episodic retrieval
    qvec = embed([message])[0]
    episodes = retrieve_episodes(db, user_id, qvec)
    # 5. compose prompt + call the model through the adapter
    messages, sections = build_prompt(sess_sum, life_sum, episodes, window, message)
    t1 = time.perf_counter()
    res = _client("reply").complete(messages)
    model_ms = (time.perf_counter() - t1) * 1000
    reply = res.text.strip()
    # 6. save the assistant reply
    db.messages.insert_one({"user_id": user_id, "session_id": session_id, "role": "assistant",
                            "content": reply, "created_at": now()})
    # 7. episodic extraction from the user message
    aux = {"aux_prompt_tokens": 0, "aux_completion_tokens": 0}
    new_eps = store_episodes(db, user_id, session_id, extract_episodes(message, aux))
    # 8. summarization trigger
    summ = maybe_summarize(db, user_id, session_id, aux)
    latency_ms = (time.perf_counter() - t0) * 1000

    usage = {
        "prompt_tokens": res.input_tokens,
        "completion_tokens": res.output_tokens,
        **sections,
        "prompt_tokens_est": sum(sections.values()),
        **aux,
        "latency_ms": round(latency_ms, 1),
        "model_latency_ms": round(model_ms, 1),
        "short_term_n": n,
        "policy": policy,
        "window_messages": len(window),
        "summary_created": summ,
        "embed_backend": _embed_backend["name"],
    }
    used = {
        "short_term": {"count": len(window), "messages": window},
        "long_term": {"session_summary": sess_sum, "lifetime_summary": life_sum},
        "episodic_facts": episodes,
    }
    _log_usage(user_id, session_id, message, usage)
    return {"reply": reply, "session_id": session_id, "used": used, "usage": usage,
            "new_episodes": new_eps}


def _log_usage(user_id, session_id, message, usage):
    try:
        config.USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(config.USAGE_LOG, "a") as f:
            f.write(json.dumps({"ts": now().isoformat(timespec="seconds"), "user_id": user_id,
                                "session_id": session_id, "message": message[:80], **usage}) + "\n")
    except OSError:
        pass
