"""HW5 Part 3 - timeouts, bounded exponential-backoff retries, seeded fault injection."""
from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Any, Callable

VERIFY_SEED = 263209


class TransientError(Exception):
    """A failure that may succeed on retry (dropped connection, injected fault...)."""


class RetryExhausted(Exception):
    def __init__(self, attempts: int, last_error: str):
        super().__init__(f"storage unavailable after {attempts} attempts (last error: {last_error})")
        self.attempts = attempts
        self.last_error = last_error


@dataclass
class RetryPolicy:
    max_attempts: int = 3        # 1 try + 2 retries
    timeout_s: float = 1.0       # per attempt
    base_delay_s: float = 0.05   # backoff: 0.05s, 0.10s, 0.20s ... (doubles)
    max_delay_s: float = 0.4     # never wait longer than this between attempts


_pool = ThreadPoolExecutor(max_workers=4)


def call_with_retry(fn: Callable[[], Any], policy: RetryPolicy = RetryPolicy(),
                    sleep: Callable[[float], None] = time.sleep,
                    on_attempt: Callable[[int, str], None] | None = None) -> tuple[Any, int]:
    """Run fn with a per-attempt timeout and bounded exponential backoff.

    Returns (result, attempts_used). Raises RetryExhausted when every attempt failed.
    """
    last = ""
    for attempt in range(1, policy.max_attempts + 1):
        try:
            result = _pool.submit(fn).result(timeout=policy.timeout_s)
            if on_attempt:
                on_attempt(attempt, "ok")
            return result, attempt
        except FutureTimeout:
            last = f"timeout after {policy.timeout_s}s"
        except (TransientError, ConnectionError, OSError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        if on_attempt:
            on_attempt(attempt, last)
        if attempt < policy.max_attempts:
            sleep(min(policy.base_delay_s * 2 ** (attempt - 1), policy.max_delay_s))
    raise RetryExhausted(policy.max_attempts, last)


class FaultyStore:
    """Wraps a store and fails each call with probability `failure_rate`.

    The random generator is seeded (VERIFY_SEED), so the same seed always gives
    the same success/failure sequence.
    """

    def __init__(self, store, failure_rate: float, seed: int = VERIFY_SEED,
                 latency_s: float = 0.002):
        self.store, self.rate, self.latency_s = store, failure_rate, latency_s
        self.rng = random.Random(seed)
        self.injected = 0

    def _maybe_fail(self):
        time.sleep(self.latency_s)                 # simulated network latency
        if self.rng.random() < self.rate:
            self.injected += 1
            raise TransientError("injected fault")

    def search(self, *a):
        self._maybe_fail(); return self.store.search(*a)

    def get(self, *a):
        self._maybe_fail(); return self.store.get(*a)

    def stats(self, *a):
        self._maybe_fail(); return self.store.stats(*a)


class ResilientStore:
    """Applies call_with_retry to every storage call; remembers attempts of the last call."""

    def __init__(self, store, policy: RetryPolicy = RetryPolicy(), sleep=time.sleep):
        self.store, self.policy, self.sleep = store, policy, sleep
        self.last_attempts = 0

    def _call(self, method: str, *args):
        result, self.last_attempts = call_with_retry(
            lambda: getattr(self.store, method)(*args), self.policy, self.sleep)
        return result

    def search(self, *a):
        return self._call("search", *a)

    def get(self, *a):
        return self._call("get", *a)

    def stats(self, *a):
        return self._call("stats", *a)
