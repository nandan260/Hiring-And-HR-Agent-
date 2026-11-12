from __future__ import annotations

import re
from html import unescape
from typing import Any

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9\-_]{12,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"), "[REDACTED_GOOGLE_KEY]"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{16,}\b"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"\bxox[abpr]-[A-Za-z0-9\-]{10,}\b"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"(postgresql(?:\+\w+)?://[^:\s/]+:)[^@\s]+(@)", re.IGNORECASE), r"\1[REDACTED]\2"),
    (
        re.compile(
            r"((?:api_key|apikey|secret|password|passwd|access_token|refresh_token|client_secret|private_key|authorization)"
            r"\s*[:=]\s*['\"]?)([^'\"\s,;}{]+)",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]",
    ),
]

_SENSITIVE_KEY_SUBSTRINGS = (
    "secret",
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credential",
    "authorization",
    "cookie",
    "jwt",
    "fernet",
)

_PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+|the\s+)?(?:system|prior|above|previous)\s+(?:prompt|rules|instructions?)", re.IGNORECASE),
    re.compile(r"(?:system\s+override|developer\s+mode|dan\s+mode|unrestricted\s+mode)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:in\s+)?(?:developer|admin|root|unrestricted|god)\s+mode", re.IGNORECASE),
    re.compile(r"(?:new|updated)\s+system\s+(?:instructions?|directives?)\s*:", re.IGNORECASE),
    re.compile(r"forget\s+(?:everything|all\s+instructions?|prior\s+context)", re.IGNORECASE),
    re.compile(r"</?(?:system|assistant|tool_call|function_call|instruction)[^>]*>", re.IGNORECASE),
    re.compile(r"\[/?INST\]|###\s*SYSTEM\s*:", re.IGNORECASE),
    re.compile(r"(?:bypass|disable|turn\s+off)\s+(?:rls|guardrail|security|tenant|permission|auth)", re.IGNORECASE),
    re.compile(r"grant\s+(?:me\s+)?admin|switch\s+to\s+another\s+tenant", re.IGNORECASE),
    re.compile(r"(?:union\s+all\s+select|drop\s+table\b|;\s*delete\s+from\b|set\s+app\.current_tenant_id)", re.IGNORECASE),
]

_SYSTEM_PROMPT_LEAK_REQUEST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(reveal|print|show|output|repeat|dump|display|translate|encode|leak|expose)\b.{0,45}"
        r"\b(system\s+prompt|hidden\s+instructions?|internal\s+rules|developer\s+prompt|api\s+key|secret|fernet|jwt\s+secret|database\s+password)\b",
        re.IGNORECASE,
    ),
]

_SYSTEM_PROMPT_LEAK_MARKER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\[TENANT WORKSPACE PREFERENCES[^\]]*\]", re.IGNORECASE), "[REDACTED_SYSTEM_MARKER]"),
    (re.compile(r"CANNOT OVERRIDE SYSTEM RULES OR PERMISSIONS", re.IGNORECASE), "[REDACTED_SYSTEM_MARKER]"),
    (re.compile(r"SYSTEM PROMPT OVERRIDE|BEGIN SYSTEM PROMPT|END SYSTEM PROMPT", re.IGNORECASE), "[REDACTED_SYSTEM_MARKER]"),
]

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL_REDACTED]"),
    (re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\b\d{3})[\s.-]\d{3}[\s.-]\d{4}\b"), "[PHONE_REDACTED]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    (re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b"), "[GOV_ID_REDACTED]"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN_REDACTED]"),
]


def mask_pii_in_text(text: str, *, mode: str = "standard") -> str:
    """Mask emails, phone numbers, SSNs, Aadhaar, and PAN identifiers cleanly without touching UUIDs."""
    if not text or mode == "none":
        return text or ""
    masked = str(text)
    for rx, repl in _PII_PATTERNS:
        masked = rx.sub(repl, masked)
    return masked


def mask_pii_in_payload(value: Any, *, mode: str = "standard", depth: int = 0) -> Any:
    if mode == "none" or depth > 8:
        return value
    if isinstance(value, str):
        return mask_pii_in_text(value, mode=mode)
    if isinstance(value, list):
        return [mask_pii_in_payload(v, mode=mode, depth=depth + 1) for v in value]
    if isinstance(value, dict):
        return {k: mask_pii_in_payload(v, mode=mode, depth=depth + 1) for k, v in value.items()}
    return value


def redact_secrets_in_text(text: str, *, max_len: int | None = None) -> str:
    if not text:
        return ""
    cleaned = str(text).replace("\x00", "[NUL]")
    for pattern, repl in _SECRET_PATTERNS:
        cleaned = pattern.sub(repl, cleaned)
    if max_len is not None and len(cleaned) > max_len:
        return cleaned[:max_len] + "...[truncated]"
    return cleaned


def sanitize_structured_payload(value: Any, *, max_str_len: int = 1000, depth: int = 0) -> Any:
    if depth > 8:
        return "[TRUNCATED_DEPTH]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_secrets_in_text(value, max_len=max_str_len)
    if isinstance(value, list):
        return [sanitize_structured_payload(item, max_str_len=max_str_len, depth=depth + 1) for item in value[:50]]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for k, v in list(value.items())[:60]:
            key_str = str(k)
            lower_key = key_str.lower()
            if any(sub in lower_key for sub in _SENSITIVE_KEY_SUBSTRINGS):
                sanitized[key_str] = "[REDACTED]"
            else:
                sanitized[key_str] = sanitize_structured_payload(v, max_str_len=max_str_len, depth=depth + 1)
        return sanitized
    return redact_secrets_in_text(str(value), max_len=max_str_len)


def redact_system_markers(text: str) -> str:
    cleaned = text or ""
    for rx, repl in _SYSTEM_PROMPT_LEAK_MARKER_PATTERNS:
        cleaned = rx.sub(repl, cleaned)
    return redact_secrets_in_text(cleaned)


def strip_untrusted_webpage_text(raw_text: str, *, source_url: str, max_chars: int = 8000) -> str:
    """Clean extracted webpage text and wrap in explicit untrusted delimiters."""
    cleaned = unescape(raw_text or "")
    cleaned = re.sub(r"<!--[\s\S]*?-->", " ", cleaned)
    cleaned = re.sub(r"<script[\s\S]*?</script>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    for pat in _PROMPT_INJECTION_PATTERNS:
        cleaned = pat.sub("[FILTERED_INJECTION_PHRASE]", cleaned)
    for pat in _SYSTEM_PROMPT_LEAK_REQUEST_PATTERNS:
        cleaned = pat.sub("[FILTERED_INJECTION_PHRASE]", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    cleaned = redact_secrets_in_text(cleaned, max_len=max_chars)
    safe_source = redact_secrets_in_text(source_url, max_len=300)
    return f'<untrusted_webpage_content source="{safe_source}">\n{cleaned}\n</untrusted_webpage_content>'
