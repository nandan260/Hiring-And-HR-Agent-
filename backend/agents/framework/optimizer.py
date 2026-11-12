"""Honest token optimization, model tier routing, tenant-scoped caching, and real A/B measurement."""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import math
import re
import threading
import time
from typing import Any, Iterator, Optional
import uuid

from app.config import get_settings

# Reference cost USD per 1M tokens (input, output). Offline rule tier is zero cost.
MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "deterministic-hr-synthesizer-v1": (0.0, 0.0),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 5.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "claude-3-5-haiku-latest": (0.80, 4.00),
    "claude-3-7-sonnet-latest": (3.00, 15.00),
}

_CACHEABLE_READ_WORKFLOWS = {"hr-policy-support", "jd-generator", "hr-analytics"}

_CURRENT_EXECUTION_SCOPE: ContextVar[Optional[dict[str, Any]]] = ContextVar(
    "hireflow_optimizer_execution_scope", default=None
)


def get_current_optimizer_scope() -> Optional[dict[str, Any]]:
    return _CURRENT_EXECUTION_SCOPE.get()


@contextmanager
def optimizer_execution_scope(scope_data: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Bind mutable execution telemetry for the current LangGraph workflow turn."""
    token = _CURRENT_EXECUTION_SCOPE.set(scope_data)
    try:
        yield scope_data
    finally:
        _CURRENT_EXECUTION_SCOPE.reset(token)


def count_tokens(value: Any) -> int:
    """Deterministic sub-4-char token counter used identically for baseline and optimized measurements."""
    if value is None:
        return 0
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, default=str)
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def estimate_cost_usd(
    model_used: str,
    input_tokens: int,
    output_tokens: int,
    *,
    cached_tokens: int = 0,
    provider_used: str = "",
) -> float:
    if provider_used.startswith("deterministic") or model_used.startswith("deterministic"):
        return 0.0
    in_rate, out_rate = MODEL_PRICING_PER_1M.get(model_used, (0.15, 0.60))
    billable_in = max(0, input_tokens - max(0, cached_tokens))
    cached_discount_rate = in_rate * 0.25
    cost = (billable_in * in_rate + max(0, cached_tokens) * cached_discount_rate + max(0, output_tokens) * out_rate) / 1_000_000
    return round(cost, 6)


def select_routed_model(
    *,
    provider: str,
    workflow_slug: str,
    user_prompt: str,
    context_data: dict[str, Any],
    override_tier: Optional[str] = None,
    explicit_model: Optional[str] = None,
) -> tuple[str, str]:
    """Route simple queries to fast/rule models and complex multi-candidate synthesis to reasoning models."""
    if provider == "deterministic":
        return "tier_0_rule", explicit_model or "deterministic-hr-synthesizer-v1"

    tier_pref = (override_tier or "").strip().lower()
    lower = (user_prompt or "").lower()
    is_complex = (
        tier_pref in {"reasoning", "tier_2", "pro"}
        or workflow_slug in {"candidate-shortlisting", "hr-analytics"}
        and (
            len(context_data.get("ranked_candidates") or context_data.get("evaluated_candidates") or []) >= 3
            or any(k in lower for k in ("compare", "audit", "tradeoff", "executive", "justify", "benchmark"))
        )
    )

    if explicit_model:
        tier = "tier_2_reasoning" if is_complex else "tier_1_fast"
        return tier, explicit_model

    if provider == "gemini":
        return ("tier_2_reasoning", "gemini-2.5-pro") if is_complex else ("tier_1_fast", "gemini-2.5-flash")
    if provider == "openai":
        return ("tier_2_reasoning", "gpt-4o") if is_complex else ("tier_1_fast", "gpt-4o-mini")
    if provider == "anthropic":
        return (
            ("tier_2_reasoning", "claude-3-7-sonnet-latest")
            if is_complex
            else ("tier_1_fast", "claude-3-5-haiku-latest")
        )
    return "tier_0_rule", "deterministic-hr-synthesizer-v1"


class TenantAwareResponseCache:
    """Thread-safe TTL LRU cache partitioned by tenant, role, workflow, and blind-screening mode."""

    def __init__(self, *, max_entries: int = 400, ttl_seconds: int = 180) -> None:
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._entries: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()

    @staticmethod
    def build_key(
        *,
        tenant_id: uuid.UUID | str,
        actor_role: str,
        workflow_slug: str,
        blind_mode: bool,
        system_prompt: str,
        user_prompt: str,
        context_data: dict[str, Any],
    ) -> str:
        payload = json.dumps(
            {
                "sys": system_prompt,
                "usr": user_prompt,
                "ctx": context_data,
            },
            sort_keys=True,
            default=str,
        )
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{tenant_id}|{actor_role}|{workflow_slug}|{int(blind_mode)}|{digest}"

    def get(self, key: str) -> Optional[dict[str, Any]]:
        now = time.monotonic()
        with self._lock:
            row = self._entries.get(key)
            if row is None:
                return None
            expires_at, value = row
            if expires_at <= now:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return dict(value)

    def set(self, key: str, value: dict[str, Any]) -> None:
        now = time.monotonic()
        with self._lock:
            self._entries[key] = (now + self._ttl, dict(value))
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def invalidate_tenant(self, tenant_id: uuid.UUID | str) -> int:
        prefix = f"{tenant_id}|"
        removed = 0
        with self._lock:
            for k in list(self._entries.keys()):
                if k.startswith(prefix):
                    self._entries.pop(k, None)
                    removed += 1
        return removed

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


tenant_response_cache = TenantAwareResponseCache()


def compress_system_prompt(system_prompt: str) -> tuple[str, bool]:
    """Remove redundant blank lines, markdown dividers, and excess indentation without altering directives."""
    original = system_prompt or ""
    lines = []
    for line in original.splitlines():
        stripped = re.sub(r"[ \t]{2,}", " ", line.strip())
        if not stripped or re.fullmatch(r"[-=*_]{3,}", stripped):
            continue
        lines.append(stripped)
    compressed = "\n".join(lines)
    return compressed, len(compressed) < len(original)


def summarize_conversation_history(
    history: list[dict[str, str]],
    *,
    window: int = 4,
    max_summary_chars: int = 520,
) -> tuple[list[dict[str, str]], str, bool]:
    """Preserve recent window verbatim and distill older conversation turns cleanly."""
    if not history or window <= 0:
        return [], "", False
    recent = history[-window:]
    older = history[:-window]
    if not older:
        return recent, "", False
    bullets = []
    for msg in older[-6:]:
        role = msg.get("role", "user")
        snippet = re.sub(r"\s+", " ", (msg.get("content") or "")).strip()[:95]
        if snippet:
            bullets.append(f"{role}: {snippet}")
    summary = " | ".join(bullets)[:max_summary_chars]
    return recent, summary, bool(summary)


def filter_and_compress_context(
    context_data: dict[str, Any],
    *,
    max_chunks: int = 4,
    max_chunk_chars: int = 460,
    max_text_chars: int = 1600,
) -> tuple[dict[str, Any], list[str]]:
    """Prune redundant retrieved chunks, vector fields, and verbose whitespace inside structured tool outputs."""
    methods: list[str] = []

    def _clean(obj: Any, key_name: str = "", depth: int = 0) -> Any:
        if depth > 6:
            return obj
        if isinstance(obj, dict):
            cleaned_dict: dict[str, Any] = {}
            for k, v in obj.items():
                if k in {"embedding", "raw_bytes", "file_bytes"}:
                    methods.append("vector_blob_pruning")
                    continue
                if k in {"retrieved_chunks", "chunks", "knowledge_chunks"} and isinstance(v, list):
                    trimmed = v[:max_chunks]
                    if len(v) > len(trimmed):
                        methods.append("semantic_chunk_filtering")
                    cleaned_dict[k] = [_clean(item, k, depth + 1) for item in trimmed]
                    continue
                if k in {"history", "conversation_history"} and isinstance(v, list) and len(v) > 4:
                    cleaned_dict[k] = [_clean(item, k, depth + 1) for item in v[-4:]]
                    methods.append("history_window_trimming")
                    continue
                cleaned_dict[k] = _clean(v, k, depth + 1)
            return cleaned_dict
        if isinstance(obj, list):
            return [_clean(item, key_name, depth + 1) for item in obj[:15]]
        if isinstance(obj, str):
            norm = re.sub(r"[ \t]{2,}", " ", obj).strip()
            norm = re.sub(r"\n{3,}", "\n\n", norm)
            limit = max_chunk_chars if key_name in {"excerpt", "content"} else max_text_chars
            if len(norm) > limit:
                methods.append("context_truncation")
                return norm[:limit].rstrip() + "..."
            return norm
        return obj

    optimized_ctx = _clean(dict(context_data or {}))
    return optimized_ctx, sorted(set(methods))


def prepare_optimized_llm_request(
    *,
    system_prompt: str,
    user_prompt: str,
    context_data: dict[str, Any],
    provider: str,
    workflow_slug: str,
    optimization_enabled: bool,
    model_tier_override: Optional[str] = None,
    explicit_model: Optional[str] = None,
) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    """
    Measure exact unoptimized `baseline_input_tokens`, apply real context optimizations when enabled,
    and return `(opt_sys, opt_user, opt_ctx, telemetry_meta)`.
    """
    baseline_tokens = (
        count_tokens(system_prompt)
        + count_tokens(user_prompt)
        + count_tokens(context_data or {})
    )

    tier, selected_model = select_routed_model(
        provider=provider,
        workflow_slug=workflow_slug,
        user_prompt=user_prompt,
        context_data=context_data or {},
        override_tier=model_tier_override,
        explicit_model=explicit_model,
    )

    if not optimization_enabled:
        optimized_tokens = baseline_tokens
        return (
            system_prompt,
            user_prompt,
            dict(context_data or {}),
            {
                "baseline_input_tokens": baseline_tokens,
                "optimized_input_tokens": optimized_tokens,
                "tokens_saved": 0,
                "reduction_percent": 0.0,
                "methods_used": [],
                "model_tier": tier,
                "selected_model": selected_model,
                "cacheable": False,
            },
        )

    methods: list[str] = []
    opt_sys, sys_compressed = compress_system_prompt(system_prompt)
    if sys_compressed:
        methods.append("prompt_compression")

    opt_user = re.sub(r"[ \t]{2,}", " ", (user_prompt or "").strip())
    opt_user = re.sub(r"\n{3,}", "\n\n", opt_user)
    if len(opt_user) < len(user_prompt or ""):
        methods.append("whitespace_compaction")

    opt_ctx, ctx_methods = filter_and_compress_context(context_data or {})
    methods.extend(ctx_methods)

    if workflow_slug in _CACHEABLE_READ_WORKFLOWS and get_settings().ENABLE_RESPONSE_CACHE:
        methods.append("cache_eligible")

    methods.append(f"model_routing:{tier}")

    optimized_tokens = count_tokens(opt_sys) + count_tokens(opt_user) + count_tokens(opt_ctx)
    tokens_saved = max(0, baseline_tokens - optimized_tokens)
    reduction_pct = round((tokens_saved / baseline_tokens) * 100.0, 2) if baseline_tokens > 0 else 0.0

    return (
        opt_sys,
        opt_user,
        opt_ctx,
        {
            "baseline_input_tokens": baseline_tokens,
            "optimized_input_tokens": optimized_tokens,
            "tokens_saved": tokens_saved,
            "reduction_percent": reduction_pct,
            "methods_used": list(dict.fromkeys(methods)),
            "model_tier": tier,
            "selected_model": selected_model,
            "cacheable": workflow_slug in _CACHEABLE_READ_WORKFLOWS,
        },
    )
