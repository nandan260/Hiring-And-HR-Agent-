"""Per-tenant and per-user sliding-window rate limiter for executions and token throughput."""

from __future__ import annotations

from collections import defaultdict, deque
import threading
import time
import uuid

from ..config import get_settings


class SlidingWindowRateLimiter:
    """Thread-safe 60-second sliding-window rate limiter keyed by tenant, user, and endpoint bucket."""

    def __init__(self, window_seconds: int = 60) -> None:
        self._window = window_seconds
        self._lock = threading.Lock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._tokens: dict[str, deque[tuple[float, int]]] = defaultdict(deque)

    def _prune(self, key: str, now: float) -> None:
        cutoff = now - self._window
        req_q = self._requests[key]
        while req_q and req_q[0] <= cutoff:
            req_q.popleft()
        tok_q = self._tokens[key]
        while tok_q and tok_q[0][0] <= cutoff:
            tok_q.popleft()

    def check_and_consume(
        self,
        *,
        tenant_id: uuid.UUID | str,
        user_id: uuid.UUID | str,
        bucket: str = "agent_execute",
        estimated_tokens: int = 0,
    ) -> tuple[bool, int, str]:
        """Return `(allowed, retry_after_seconds, reason)` and record current request if allowed."""
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED:
            return True, 0, ""

        key = f"{tenant_id}:{user_id}:{bucket}"
        now = time.monotonic()

        with self._lock:
            self._prune(key, now)
            req_q = self._requests[key]
            tok_q = self._tokens[key]

            max_reqs = max(1, int(settings.RATE_LIMIT_EXECUTIONS_PER_MINUTE))
            if len(req_q) >= max_reqs:
                oldest = req_q[0]
                retry_after = max(1, int(self._window - (now - oldest)) + 1)
                return (
                    False,
                    retry_after,
                    f"Rate limit exceeded: max {max_reqs} executions per minute allowed for this user.",
                )

            max_toks = max(1000, int(settings.RATE_LIMIT_TOKENS_PER_MINUTE))
            used_tokens = sum(t for _, t in tok_q)
            if used_tokens + max(0, estimated_tokens) > max_toks:
                oldest_tok = tok_q[0][0] if tok_q else now
                retry_after = max(1, int(self._window - (now - oldest_tok)) + 1)
                return (
                    False,
                    retry_after,
                    f"Token throughput limit exceeded ({used_tokens} tokens in last 60s; limit {max_toks}/min).",
                )

            req_q.append(now)
            if estimated_tokens > 0:
                tok_q.append((now, int(estimated_tokens)))
            return True, 0, ""

    def record_tokens(
        self,
        *,
        tenant_id: uuid.UUID | str,
        user_id: uuid.UUID | str,
        tokens: int,
        bucket: str = "agent_execute",
    ) -> None:
        if tokens <= 0:
            return
        key = f"{tenant_id}:{user_id}:{bucket}"
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._tokens[key].append((now, int(tokens)))

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._tokens.clear()


rate_limiter = SlidingWindowRateLimiter()
