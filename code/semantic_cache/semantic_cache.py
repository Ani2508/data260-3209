"""HW9 Part 2: semantic response cache stored in Redis with a vector index.

Each entry is a Redis hash under s3209:semcache:<id> holding the query, its embedding
(FLOAT32, normalized), the final answer and a data-version marker. A lookup runs a
KNN search with cosine distance; similarity = 1 - distance.
"""
from __future__ import annotations

import time
import uuid

import numpy as np
from redis.commands.search.field import TextField, VectorField
from redis.commands.search.query import Query
from redis.exceptions import ResponseError

try:
    from redis.commands.search.index_definition import IndexDefinition, IndexType
except ImportError:  # redis-py < 6
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType

PREFIX = "s3209"
INDEX = f"{PREFIX}_semcache_idx"
KEY_PREFIX = f"{PREFIX}:semcache:"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_THRESHOLD = 0.85
FIELDS = ("query", "answer", "data_version", "trial_ids", "review", "created_at")


def similarity_from_distance(distance: float | str) -> float:
    """Return cosine similarity from a RediSearch COSINE distance (distance = 1 - cos)."""
    return round(1.0 - float(distance), 4)


class Embedder:
    """SentenceTransformers model that turns text into a normalized FLOAT32 vector."""

    def __init__(self, model_name: str = EMBED_MODEL) -> None:
        """Return nothing; load the model once and record its dimension."""
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dim = len(self.model.encode("dimension check"))

    def encode(self, text: str) -> bytes:
        """Return the normalized embedding of text as FLOAT32 bytes for Redis."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be a non-empty string")
        vec = self.model.encode(text, normalize_embeddings=True)
        return np.asarray(vec, dtype=np.float32).tobytes()


class SemanticCache:
    """Redis vector index of previous queries and their final answers."""

    def __init__(self, redis_client, dim: int, threshold: float = DEFAULT_THRESHOLD) -> None:
        """Return nothing; keep the client, vector size and hit threshold."""
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.r = redis_client
        self.dim = dim
        self.threshold = threshold

    def ensure_index(self) -> bool:
        """Return True if the vector index was created now, False if it already existed."""
        try:
            self.r.ft(INDEX).info()
            return False
        except ResponseError:
            schema = (TextField("query"), TextField("data_version"),
                      VectorField("embedding", "FLAT", {"TYPE": "FLOAT32", "DIM": self.dim,
                                                        "DISTANCE_METRIC": "COSINE"}))
            self.r.ft(INDEX).create_index(
                schema, definition=IndexDefinition(prefix=[KEY_PREFIX], index_type=IndexType.HASH))
            return True

    def reset(self) -> int:
        """Return the number of cache entries deleted (the index itself is kept)."""
        keys = list(self.r.scan_iter(match=f"{KEY_PREFIX}*"))
        if keys:
            self.r.delete(*keys)
        return len(keys)

    def nearest(self, vec: bytes) -> dict | None:
        """Return the closest cached entry with its similarity, or None if the cache is empty."""
        q = (Query("*=>[KNN 1 @embedding $vec AS distance]").sort_by("distance")
             .return_fields(*FIELDS, "distance").dialect(2))
        docs = self.r.ft(INDEX).search(q, query_params={"vec": vec}).docs
        if not docs:
            return None
        doc = docs[0]
        entry = {f: getattr(doc, f, "") for f in FIELDS}
        entry["key"] = doc.id
        entry["similarity"] = similarity_from_distance(doc.distance)
        return entry

    def store(self, query: str, vec: bytes, answer: str, data_version: str,
              trial_ids: list[int], review: str = "") -> str:
        """Return the Redis key of the new entry holding query, embedding, answer and version."""
        if len(vec) != self.dim * 4:
            raise ValueError(f"embedding must be {self.dim} FLOAT32 values")
        key = f"{KEY_PREFIX}{uuid.uuid4().hex[:12]}"
        self.r.hset(key, mapping={
            "query": query, "embedding": vec, "answer": answer,
            "data_version": data_version, "trial_ids": ",".join(map(str, trial_ids)),
            "review": review, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")})
        return key

    def delete(self, key: str) -> bool:
        """Return True if the cache entry was removed (used by invalidation)."""
        if not key.startswith(KEY_PREFIX):
            raise ValueError(f"key must start with {KEY_PREFIX}")
        return bool(self.r.delete(key))
