"""Malicious document detection & untrusted text neutralization for resumes and KB uploads."""

from __future__ import annotations

from dataclasses import dataclass, field
import io
from pathlib import Path
import re
import zipfile

from app.runtime.redaction import (
    _PROMPT_INJECTION_PATTERNS,
    _SYSTEM_PROMPT_LEAK_REQUEST_PATTERNS,
    redact_secrets_in_text,
)

_EXECUTABLE_MAGICS: list[tuple[bytes, str]] = [
    (b"MZ", "Windows PE/MZ executable header"),
    (b"\x7fELF", "Linux ELF executable header"),
    (b"\xfe\xed\xfa\xce", "Mach-O executable header"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit executable header"),
    (b"\xca\xfe\xba\xbe", "Universal Mach-O / Java class header"),
    (b"#!", "Executable script shebang header"),
]

_PDF_HAZARD_TOKENS: list[tuple[bytes, str]] = [
    (b"/JavaScript", "Embedded PDF JavaScript action"),
    (b"/JS", "Embedded PDF JS action"),
    (b"/Launch", "PDF Launch command action"),
    (b"/OpenAction", "Automatic PDF OpenAction script trigger"),
    (b"/RichMedia", "Embedded RichMedia active payload"),
    (b"/EmbeddedFile", "Suspicious embedded file stream in PDF"),
]

_SCRIPT_SMUGGLING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"<script\b[^>]*>[\s\S]*?</script>", re.IGNORECASE), "Embedded <script> tag"),
    (re.compile(r"<iframe\b[^>]*>|javascript\s*:", re.IGNORECASE), "Active iframe or javascript: URI"),
    (re.compile(r"\bon(?:error|load|click|mouseover)\s*=\s*['\"]", re.IGNORECASE), "Inline DOM event handler"),
    (re.compile(r"<\?php\b", re.IGNORECASE), "Embedded server-side PHP code"),
]

_DOC_RANKING_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?:always\s+)?rank\s+(?:this\s+candidate|me)\s+(?:first|#?1|at\s+the\s+top)", re.IGNORECASE),
    re.compile(r"(?:score|rate|give)\s+(?:me|this\s+candidate)\s*(?:a\s*)?100(?:\s*/\s*100)?", re.IGNORECASE),
    re.compile(r"override\s+(?:the\s+)?(?:scoring|evaluation|screening)\s+rubric", re.IGNORECASE),
]


@dataclass
class DocumentSecurityResult:
    is_safe_for_upload: bool
    threats_detected: list[str] = field(default_factory=list)
    indirect_injection_detected: bool = False
    blocked_reason: str = ""


def neutralize_untrusted_document_text(
    text: str,
    *,
    source_name: str = "untrusted_document",
    max_chars: int = 12000,
) -> tuple[str, list[str]]:
    """Strip prompt injections, script tags, and ranking-override phrases from untrusted CV/doc text."""
    if not text:
        return "", []
    cleaned = str(text)
    flags: list[str] = []

    for rx, _label in _SCRIPT_SMUGGLING_PATTERNS:
        if rx.search(cleaned):
            cleaned = rx.sub(" [REMOVED_SCRIPT] ", cleaned)
            if "script_smuggling_stripped" not in flags:
                flags.append("script_smuggling_stripped")

    lines_out: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line
        line_flagged = False
        for rx in _PROMPT_INJECTION_PATTERNS + _SYSTEM_PROMPT_LEAK_REQUEST_PATTERNS + _DOC_RANKING_INJECTION_PATTERNS:
            if rx.search(line):
                line = rx.sub("[FILTERED_UNTRUSTED_DIRECTIVE]", line)
                line_flagged = True
        if line_flagged and "indirect_prompt_injection_neutralized" not in flags:
            flags.append("indirect_prompt_injection_neutralized")
        lines_out.append(line)

    result = redact_secrets_in_text("\n".join(lines_out).strip(), max_len=max_chars)
    return result, flags


def _scan_text_for_indirect_injection(text: str) -> list[str]:
    findings: list[str] = []
    for rx in _PROMPT_INJECTION_PATTERNS + _SYSTEM_PROMPT_LEAK_REQUEST_PATTERNS + _DOC_RANKING_INJECTION_PATTERNS:
        if rx.search(text):
            findings.append(f"Indirect prompt injection phrase matched ({rx.pattern[:48]})")
            break
    for rx, label in _SCRIPT_SMUGGLING_PATTERNS:
        if rx.search(text):
            findings.append(label)
            break
    return findings


def inspect_document_bytes(
    raw_bytes: bytes,
    *,
    filename: str,
    mime_type: str = "",
    extracted_text: str = "",
    allow_indirect_text_neutralization: bool = False,
) -> DocumentSecurityResult:
    """
    Scan uploaded files prior to persistence: blocks disguised executables, PDF JS/Launch actions,
    DOCX zip-slip / zip-bombs / VBA macros / XXE entities, script smuggling, and indirect prompt injection.
    """
    threats: list[str] = []
    ext = Path(filename or "").suffix.lower()
    head = raw_bytes[:64]

    # 1. Executable / script header masquerading as HR document
    for magic, desc in _EXECUTABLE_MAGICS:
        if head.startswith(magic):
            threats.append(f"Disguised executable blocked: {desc}")

    # 2. PDF active exploit / action token check
    if ext == ".pdf" or mime_type == "application/pdf" or raw_bytes.lstrip().startswith(b"%PDF"):
        for token, desc in _PDF_HAZARD_TOKENS:
            if token in raw_bytes:
                threats.append(f"Malicious PDF content blocked: {desc}")

    # 3. DOCX archive & XML safety check
    if ext == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                total_uncompressed = 0
                for info in zf.infolist():
                    if ".." in info.filename or info.filename.startswith(("/", "\\")):
                        threats.append(f"DOCX archive path traversal detected: {info.filename}")
                        break
                    total_uncompressed += info.file_size
                    if total_uncompressed > 25 * 1024 * 1024:
                        threats.append("DOCX zip-bomb size limit exceeded")
                        break
                    lower_name = info.filename.lower()
                    if "vbaproject.bin" in lower_name or lower_name.endswith(".bin"):
                        threats.append("DOCX macro binary (vbaProject.bin) is not permitted")
                        break
                    if lower_name.endswith(".xml") or lower_name.endswith(".rels"):
                        xml_sample = zf.read(info.filename)[:16384]
                        if b"<!ENTITY" in xml_sample or b"<!DOCTYPE" in xml_sample:
                            threats.append("DOCX XML External Entity (XXE) declaration blocked")
                            break
        except zipfile.BadZipFile:
            threats.append("Corrupted or invalid DOCX archive structure")

    # 4. Scan extracted or plain-text content for scripts & indirect injections
    text_sample = extracted_text
    if not text_sample and ext in {".txt", ".md", ".csv"}:
        if b"\x00" in raw_bytes[:65_536]:
            threats.append("Binary/NUL bytes found in plain-text document upload.")
        text_sample = raw_bytes[:200_000].decode("utf-8", errors="replace")

    if ext in {".txt", ".md", ".csv"}:
        alnum_count = len(re.findall(r"[A-Za-z0-9]", text_sample))
        replacement_count = text_sample.count("\ufffd")
        if replacement_count > max(5, len(text_sample) * 0.08):
            threats.append("Corrupted or unreadable binary content detected in text document.")
        elif alnum_count < 8:
            threats.append("Uploaded text document or resume is empty or contains insufficient readable text.")
    elif extracted_text:
        alnum_count = len(re.findall(r"[A-Za-z0-9]", extracted_text))
        replacement_count = extracted_text.count("\ufffd")
        if replacement_count > max(5, len(extracted_text) * 0.08) or "\x00" in extracted_text:
            threats.append("Corrupted or binary-damaged document: extracted stream contains invalid characters.")
        elif alnum_count < 8:
            threats.append("Uploaded document or resume contains no readable text content.")

    indirect_detected = False
    if text_sample:
        text_findings = _scan_text_for_indirect_injection(text_sample)
        if text_findings:
            indirect_detected = True
            if not allow_indirect_text_neutralization:
                threats.extend(text_findings)

    if threats:
        return DocumentSecurityResult(
            is_safe_for_upload=False,
            threats_detected=threats,
            indirect_injection_detected=indirect_detected,
            blocked_reason=f"Security scan blocked file '{filename}': {'; '.join(threats)}",
        )
    return DocumentSecurityResult(
        is_safe_for_upload=True,
        threats_detected=[],
        indirect_injection_detected=indirect_detected,
        blocked_reason="",
    )
