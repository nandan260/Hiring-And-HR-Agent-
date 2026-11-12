"""Centralized AI guardrails: injection scanning, input validation, HR safety, and PII/secret scrubbing."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

from app.runtime.redaction import (
    _PROMPT_INJECTION_PATTERNS,
    _SYSTEM_PROMPT_LEAK_REQUEST_PATTERNS,
    mask_pii_in_payload,
    mask_pii_in_text,
    redact_secrets_in_text,
    redact_system_markers,
    sanitize_structured_payload,
)

PROTECTED_BIAS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(rank|filter|prefer|prioritize|reject|exclude|penalize|shortlist|hire|avoid|only\s+select)\b.{0,55}"
        r"\b(age|older|younger|male|female|women|men|gender|religion|muslim|christian|hindu|jewish|sikh|caste|disability|disabled|ethnicity|race|married|pregnant|marital\s+status|sexual\s+orientation)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(no|only|exclude)\s+(candidates?\s+)?(under|over|older\s+than|younger\s+than)\s+\d{2}\s*(years?\s+old|yo|yrs?)?\b",
        re.IGNORECASE,
    ),
]

AUTO_REJECT_INPUT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(auto[\s-]?reject|automatically\s+reject|reject\s+without\s+(?:human|hr|manual)\s+review|"
        r"bypass\s+human\s+approval\s+and\s+reject)\b",
        re.IGNORECASE,
    ),
]

PROTECTED_OUTPUT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(rejected|lower\s+score|penalized|deprioritized)\s+due\s+to\s+(age|gender|religion|race|caste|disability|pregnancy|marital\s+status)\b", re.IGNORECASE),
    re.compile(r"\b(too\s+old|too\s+young|only\s+(?:male|female)\s+candidates\s+fit)\b", re.IGNORECASE),
]

AUTO_REJECT_OUTPUT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(auto[\s-]?rejected|automatically\s+rejected|rejected\s+automatically\s+without\s+review)\b", re.IGNORECASE),
]

_BASE64_CANDIDATE_RX = re.compile(r"\b([A-Za-z0-9+/]{24,}={0,2})\b")


def _decode_suspicious_base64_segments(text: str) -> list[str]:
    decoded_segments: list[str] = []
    for candidate in _BASE64_CANDIDATE_RX.findall(text)[:6]:
        padded = candidate + ("=" * ((4 - len(candidate) % 4) % 4))
        try:
            raw = base64.b64decode(padded, validate=False)
            if not raw or len(raw) > 2048:
                continue
            decoded = raw.decode("utf-8", errors="ignore").strip()
            printable = sum(1 for ch in decoded if 32 <= ord(ch) <= 126 or ch in "\n\r\t")
            if decoded and printable / max(1, len(decoded)) >= 0.8:
                decoded_segments.append(decoded)
        except Exception:
            continue
    return decoded_segments


def scan_prompt_injection(text: str) -> tuple[bool, str]:
    """Detect direct, role-tag, SQL/RLS exfiltration, leak-request, and base64-encoded injections."""
    raw = (text or "").strip()
    if not raw:
        return False, ""

    candidates = [raw] + _decode_suspicious_base64_segments(raw)
    for segment in candidates:
        for rx in _PROMPT_INJECTION_PATTERNS:
            if rx.search(segment):
                return True, "Prompt injection or instruction/tenant override pattern detected."
        for rx in _SYSTEM_PROMPT_LEAK_REQUEST_PATTERNS:
            if rx.search(segment):
                return True, "System prompt or internal credential extraction attempt detected."
    return False, ""


def validate_input_safety(
    prompt: str,
    *,
    max_input_tokens: int = 8000,
    structured_input: dict[str, Any] | None = None,
) -> tuple[bool, str, list[str]]:
    """Reject empty inputs, NUL/control characters, repetition bombs, and oversized payloads."""
    flags: list[str] = []
    text = prompt or ""
    if not text.strip() and not structured_input:
        return False, "Input prompt cannot be empty.", ["invalid_empty_input"]

    if "\x00" in text:
        return False, "Invalid input: NUL byte control characters are not permitted.", ["invalid_control_chars"]

    control_count = sum(1 for ch in text[:4000] if ord(ch) < 32 and ch not in ("\n", "\r", "\t"))
    if control_count > 10:
        return False, "Invalid input: excessive non-printable control characters detected.", ["invalid_control_chars"]

    max_chars = max(4000, max_input_tokens * 5)
    serialized_extra = json.dumps(structured_input, default=str) if structured_input else ""
    total_chars = len(text) + len(serialized_extra)
    est_tokens = max(1, (total_chars + 3) // 4)
    if total_chars > max_chars or est_tokens > max_input_tokens:
        return (
            False,
            f"Input exceeds safe token limit ({est_tokens} est. tokens > {max_input_tokens} max). Shorten or split the request.",
            ["excessive_input_tokens"],
        )

    # Repetition / token-exhaustion bomb check (e.g., same word repeated >120 times consecutively)
    tokens = re.findall(r"\S+", text[:12000].lower())
    if len(tokens) >= 120:
        streak = 1
        for i in range(1, len(tokens)):
            if tokens[i] == tokens[i - 1]:
                streak += 1
                if streak >= 120:
                    return (
                        False,
                        "Input rejected by token-exhaustion guardrail: excessive repeated token pattern detected.",
                        ["repetition_bomb_blocked"],
                    )
            else:
                streak = 1

    return True, "", flags


def check_hr_safety_input(
    text: str,
    structured_input: dict[str, Any] | None = None,
) -> tuple[bool, str, str]:
    """
    Enforce HR fairness & anti-auto-rejection rules before executing workflow logic.
    Returns `(allowed, flag_code, message)`.
    """
    combined = text or ""
    if structured_input:
        combined = f"{combined}\n{json.dumps(structured_input, default=str)}"

    for rx in PROTECTED_BIAS_PATTERNS:
        if rx.search(combined):
            return (
                False,
                "blocked_policy_fairness",
                "Request blocked by HR Fairness Guardrail: evaluating, filtering, or rejecting candidates using "
                "protected attributes (age, gender, religion, caste, disability, race, marital status) is strictly prohibited.",
            )

    for rx in AUTO_REJECT_INPUT_PATTERNS:
        if rx.search(combined):
            return (
                False,
                "blocked_auto_reject",
                "Request blocked by HR Safety Policy: autonomous candidate auto-rejection without human review is not permitted. "
                "Submit an evaluation request with human-in-the-loop sign-off instead.",
            )

    return True, "", ""


def scrub_output_for_secrets_and_pii(
    value: Any,
    *,
    blind_mode: bool = False,
    strict_pii_masking: bool = False,
    role: str = "business_admin",
) -> tuple[Any, list[str]]:
    """Scrub secrets/system markers from any output payload and mask PII when policy requires it."""
    flags: list[str] = []
    should_mask_pii = bool(blind_mode or strict_pii_masking or role in ("business_employee", "member"))

    def _walk(item: Any, depth: int = 0) -> Any:
        if depth > 10:
            return item
        if isinstance(item, str):
            cleaned = redact_system_markers(item)
            if cleaned != item and "system_marker_or_secret_scrubbed" not in flags:
                flags.append("system_marker_or_secret_scrubbed")
            if should_mask_pii:
                masked = mask_pii_in_text(cleaned, mode="strict")
                if masked != cleaned and "pii_masked" not in flags:
                    flags.append("pii_masked")
                return masked
            return cleaned
        if isinstance(item, list):
            return [_walk(v, depth + 1) for v in item]
        if isinstance(item, dict):
            return {k: _walk(v, depth + 1) for k, v in item.items()}
        return item

    return _walk(value), flags


def sanitize_outbound_llm_context(
    system_prompt: str,
    user_prompt: str,
    context_data: dict[str, Any],
    *,
    blind_mode: bool = False,
    strict_pii_masking: bool = False,
) -> tuple[str, str, dict[str, Any], list[str]]:
    """Scrub secrets and optionally mask PII in outbound LLM context prior to API dispatch."""
    flags: list[str] = []
    safe_ctx = sanitize_structured_payload(context_data or {}, max_str_len=2400)
    if blind_mode or strict_pii_masking:
        safe_ctx = mask_pii_in_payload(safe_ctx, mode="strict")
        safe_user = mask_pii_in_text(redact_secrets_in_text(user_prompt), mode="strict")
        flags.append("outbound_pii_masked")
    else:
        safe_user = redact_secrets_in_text(user_prompt)

    safe_sys = redact_secrets_in_text(system_prompt)
    return safe_sys, safe_user, safe_ctx, flags
