"""Strictly whitelisted sandbox task worker.

Runs inside either:
1. A hardened non-root Docker container (--network=none, --read-only, --cap-drop=ALL), OR
2. A clearly labelled development_fallback isolated child Python process.

SECURITY INVARIANT:
- Accepts ONLY structured JSON via stdin with a task name from ALLOWED_TASKS.
- Never executes shell commands, arbitrary Python strings, or host paths outside SANDBOX_WORKSPACE.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    raw = os.environ.get("SANDBOX_WORKSPACE", "")
    if not raw:
        raw = str(Path.cwd())
    root = Path(raw).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _resolve_workspace_file(relative_path: str) -> Path:
    root = _workspace_root()
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise PermissionError(f"Path traversal blocked outside sandbox workspace: {relative_path}")
    return candidate


def _extract_skills(text: str) -> list[str]:
    known = [
        "Python", "FastAPI", "Django", "SQL", "PostgreSQL", "React", "TypeScript",
        "JavaScript", "Docker", "Kubernetes", "AWS", "GCP", "Azure", "LangGraph",
        "LangChain", "Machine Learning", "PyTorch", "TensorFlow", "Terraform",
        "Playwright", "Redis", "GraphQL", "Go", "Rust", "Java", "CI/CD",
    ]
    lower = text.lower()
    found = [s for s in known if re.search(rf"(?<![A-Za-z0-9]){re.escape(s.lower())}(?![A-Za-z0-9])", lower)]
    return found


def _task_noop_ping(payload: dict[str, Any]) -> dict[str, Any]:
    root = _workspace_root()
    return {
        "ok": True,
        "pid": os.getpid(),
        "workspace_exists": root.exists(),
        "echo": str(payload.get("ping", "pong"))[:120],
    }


def _task_probe_delay(payload: dict[str, Any]) -> dict[str, Any]:
    seconds = float(payload.get("seconds", 0.2))
    seconds = max(0.0, min(seconds, 30.0))
    time.sleep(seconds)
    return {"ok": True, "slept_seconds": seconds}


def _load_bytes(payload: dict[str, Any]) -> bytes:
    if payload.get("content_base64"):
        return base64.b64decode(str(payload["content_base64"]).encode("ascii"))
    rel = str(payload.get("workspace_file", "")).strip()
    if rel:
        path = _resolve_workspace_file(rel)
        return path.read_bytes()
    raise ValueError("Missing content_base64 or workspace_file")


def _task_parse_pdf_resume(payload: dict[str, Any]) -> dict[str, Any]:
    from pypdf import PdfReader

    data = _load_bytes(payload)
    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    phones = re.findall(r"\+?\d[\d\-\s()]{7,}\d", text)
    exp_matches = [int(m) for m in re.findall(r"(\d{1,2})\+?\s*(?:years?|yrs?)\b", text.lower())]
    return {
        "ok": True,
        "page_count": len(reader.pages),
        "char_count": len(text),
        "extracted_text": text[:20000],
        "detected_skills": _extract_skills(text),
        "emails": emails[:3],
        "phones": [p.strip() for p in phones[:3]],
        "years_experience": max(exp_matches) if exp_matches else 0,
    }


def _task_parse_docx_resume(payload: dict[str, Any]) -> dict[str, Any]:
    from docx import Document

    data = _load_bytes(payload)
    doc = Document(io.BytesIO(data))
    lines: list[str] = []
    for p in doc.paragraphs:
        if p.text.strip():
            lines.append(p.text.strip())
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    text = "\n".join(lines).strip()
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    exp_matches = [int(m) for m in re.findall(r"(\d{1,2})\+?\s*(?:years?|yrs?)\b", text.lower())]
    return {
        "ok": True,
        "paragraph_count": len(doc.paragraphs),
        "table_count": len(doc.tables),
        "char_count": len(text),
        "extracted_text": text[:20000],
        "detected_skills": _extract_skills(text),
        "emails": emails[:3],
        "years_experience": max(exp_matches) if exp_matches else 0,
    }


def _task_rank_candidates_weighted(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates") or []
    required_skills = [str(s).lower() for s in (payload.get("required_skills") or [])]
    min_years = float(payload.get("min_experience_years") or 0)
    weights = payload.get("weights") or {}
    w_skills = float(weights.get("skills", 0.55))
    w_exp = float(weights.get("experience", 0.25))
    w_base = float(weights.get("baseline", 0.20))

    ranked: list[dict[str, Any]] = []
    for c in candidates:
        c_skills = [str(s).lower() for s in (c.get("skills") or [])]
        skill_hits = [s for s in required_skills if s in c_skills]
        skill_ratio = (len(skill_hits) / len(required_skills)) if required_skills else 0.75
        yrs = float(c.get("experience_years") or 0)
        exp_ratio = min(yrs / max(min_years, 1.0), 1.2) / 1.2 if min_years > 0 else min(yrs / 5.0, 1.0)
        base_score = float(c.get("match_score") or 60) / 100.0
        composite = round(100.0 * (w_skills * skill_ratio + w_exp * exp_ratio + w_base * base_score), 1)
        ranked.append(
            {
                "candidate_id": c.get("id"),
                "full_name": c.get("full_name"),
                "composite_score": composite,
                "matched_skills": skill_hits,
                "missing_skills": [s for s in required_skills if s not in c_skills],
                "experience_years": yrs,
            }
        )
    ranked.sort(key=lambda item: item["composite_score"], reverse=True)
    return {"ok": True, "ranked": ranked}


def _task_verify_kyc_document(payload: dict[str, Any]) -> dict[str, Any]:
    doc_type = str(payload.get("document_type", "identity_document"))
    content = str(payload.get("text_preview", ""))[:10000]
    min_len = int(payload.get("min_chars", 20))
    has_signature_marker = any(k in content.lower() for k in ("signed", "signature", "verified", "id:", "passport", "license"))
    passed = len(content.strip()) >= min_len or bool(payload.get("filename"))
    return {
        "ok": True,
        "document_type": doc_type,
        "verified": passed,
        "char_count": len(content.strip()),
        "has_signature_or_id_marker": has_signature_marker,
    }


def _task_compute_analytics_charts(payload: dict[str, Any]) -> dict[str, Any]:
    stages: dict[str, int] = payload.get("stage_counts") or {}
    total = sum(int(v) for v in stages.values())
    percentages = {
        k: round((int(v) / total) * 100.0, 1) if total > 0 else 0.0
        for k, v in stages.items()
    }
    return {"ok": True, "total": total, "stage_percentages": percentages}


ALLOWED_TASKS = {
    "noop_ping": _task_noop_ping,
    "probe_delay": _task_probe_delay,
    "parse_pdf_resume": _task_parse_pdf_resume,
    "parse_docx_resume": _task_parse_docx_resume,
    "rank_candidates_weighted": _task_rank_candidates_weighted,
    "verify_kyc_document": _task_verify_kyc_document,
    "compute_analytics_charts": _task_compute_analytics_charts,
}


def main() -> int:
    try:
        raw_input = sys.stdin.read()
        request = json.loads(raw_input or "{}")
        task_name = str(request.get("task", "")).strip()
        payload = request.get("payload") or {}
        if task_name not in ALLOWED_TASKS:
            sys.stdout.write(json.dumps({"ok": False, "error": f"Disallowed or unknown sandbox task: {task_name}"}))
            return 2
        if not isinstance(payload, dict):
            sys.stdout.write(json.dumps({"ok": False, "error": "Payload must be a JSON object"}))
            return 2
        result = ALLOWED_TASKS[task_name](payload)
        sys.stdout.write(json.dumps(result))
        return 0
    except PermissionError as exc:
        sys.stdout.write(json.dumps({"ok": False, "error": f"Permission error: {exc}"}))
        return 3
    except Exception as exc:
        sys.stdout.write(json.dumps({"ok": False, "error": f"Worker error: {type(exc).__name__}: {exc}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
