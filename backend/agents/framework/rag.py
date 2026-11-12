"""Tenant-isolated pgvector RAG helpers, PDF/DOCX extraction, and role-filtered chunk retrieval."""

from __future__ import annotations

import hashlib
import io
import math
import re
import uuid
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Optional

from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
import yaml

from app.db.models import KnowledgeChunk, KnowledgeDocument

EMBEDDING_DIM = 384

_FRONTMATTER_RX = re.compile(r"\A---\s*\n([\s\S]*?)\n---\s*(?:\n|$)")
_WIKILINK_RX = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_HASHTAG_RX = re.compile(r"(?:^|\s)#([a-zA-Z][a-zA-Z0-9_-]{1,40})")


def parse_obsidian_markdown(raw_text: str) -> dict[str, Any]:
    """
    Parse optional Obsidian-style YAML frontmatter (`tags`, `department`, `workflow`, `effective_date`),
    `[[Wikilinks]]`, and `#tags` while stripping frontmatter noise before embedding.
    """
    text = (raw_text or "").replace("\r\n", "\n")
    frontmatter: dict[str, Any] = {}
    body = text
    m = _FRONTMATTER_RX.match(text)
    if m:
        try:
            loaded = yaml.safe_load(m.group(1))
            if isinstance(loaded, dict):
                frontmatter = loaded
                body = text[m.end() :]
        except Exception:
            frontmatter = {}

    tags: set[str] = set()
    fm_tags = frontmatter.get("tags")
    if isinstance(fm_tags, list):
        tags.update(str(t).strip().lower() for t in fm_tags if str(t).strip())
    elif isinstance(fm_tags, str):
        tags.update(t.strip().lower() for t in fm_tags.split(",") if t.strip())
    tags.update(t.lower() for t in _HASHTAG_RX.findall(body))

    wikilinks = list(dict.fromkeys(w.strip() for w in _WIKILINK_RX.findall(body) if w.strip()))
    return {
        "frontmatter": frontmatter,
        "body_text": body.strip(),
        "tags": sorted(tags)[:20],
        "wikilinks": wikilinks[:20],
    }


def export_document_as_obsidian_markdown(doc: KnowledgeDocument, chunks: list[KnowledgeChunk]) -> str:
    """Export an indexed tenant HR document as portable Obsidian-compatible Markdown with YAML frontmatter."""
    meta = dict((chunks[0].metadata_json or {}) if chunks else {})
    tags = list(meta.get("tags") or [doc.source_type, "hireflow-hr"])
    wikilinks = list(meta.get("wikilinks") or [])
    fm: dict[str, Any] = {
        "title": doc.title,
        "source_type": doc.source_type,
        "min_role_access": doc.min_role_access,
        "original_filename": doc.original_filename,
        "sha256": doc.sha256_checksum,
        "tags": tags,
    }
    if meta.get("department"):
        fm["department"] = meta["department"]
    if meta.get("effective_date"):
        fm["effective_date"] = meta["effective_date"]
    fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()
    parts = [f"---\n{fm_yaml}\n---\n", f"# {doc.title}\n"]
    for ch in chunks:
        if ch.section_title and ch.section_title != doc.title:
            parts.append(f"## {ch.section_title}\n")
        parts.append(f"{ch.content}\n")
    if wikilinks:
        parts.append("## Related HR Notes\n" + "\n".join(f"- [[{w}]]" for w in wikilinks) + "\n")
    return "\n".join(parts).strip() + "\n"

ROLE_RANK: dict[str, int] = {
    "member": 1,
    "business_employee": 1,
    "business_admin": 2,
    "business_owner": 3,
    "platform_admin": 4,
}


def compute_text_embedding(text: str, dims: int = EMBEDDING_DIM) -> list[float]:
    """Generate a deterministic L2-normalized 384-d semantic/subword embedding vector.

    Uses BLAKE2b signed feature hashing across unigrams, bigrams, and 3-character trigrams
    so pgvector cosine similarity works deterministically without external model downloads.
    """
    vec = [0.0] * dims
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower()).strip()
    tokens = [tok for tok in cleaned.split() if tok]
    if not tokens:
        vec[0] = 1.0
        return vec

    features: list[tuple[str, float]] = []
    for i, tok in enumerate(tokens):
        features.append((f"u:{tok}", 1.5))
        if len(tok) >= 4:
            for j in range(len(tok) - 2):
                features.append((f"tri:{tok[j : j + 3]}", 0.35))
        if i + 1 < len(tokens):
            features.append((f"bi:{tok}_{tokens[i + 1]}", 1.25))

    for feat, weight in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % dims
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[idx] += sign * weight

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def extract_document_text(file_bytes: bytes, *, filename: str = "", mime_type: str = "") -> str:
    """Extract clean plain text from PDF, DOCX, Markdown, CSV, or UTF-8 documents."""
    lower_name = (filename or "").lower()
    lower_mime = (mime_type or "").lower()

    if lower_name.endswith(".pdf") or "pdf" in lower_mime or file_bytes.lstrip().startswith(b"%PDF"):
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = [page.extract_text() or "" for page in reader.pages]
            joined = "\n\n".join(p.strip() for p in pages if p.strip())
            if joined.strip():
                return joined
        except Exception:
            pass
        if b"\x00" in file_bytes[:65_536]:
            return ""
        decoded_pdf = file_bytes.decode("utf-8", errors="replace").strip()
        if decoded_pdf.count("\ufffd") > max(3, int(len(decoded_pdf) * 0.05)):
            return ""
        stripped_markers = re.sub(r"%PDF-[\d.]+|%%EOF", "", decoded_pdf)
        if len(re.findall(r"[A-Za-z0-9]", stripped_markers)) < 8:
            return ""
        return decoded_pdf

    if lower_name.endswith(".docx") or "wordprocessingml" in lower_mime:
        try:
            from docx import Document

            doc = Document(io.BytesIO(file_bytes))
            doc_lines: list[str] = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if cells:
                        doc_lines.append(" | ".join(cells))
            if doc_lines:
                return "\n".join(doc_lines)
        except Exception:
            pass
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                if "word/document.xml" in zf.namelist():
                    root = ET.fromstring(zf.read("word/document.xml"))
                    paragraphs: list[str] = []
                    for elem in root.iter():
                        if elem.tag.endswith("}p"):
                            texts = [t.text for t in elem.iter() if t.tag.endswith("}t") and t.text]
                            if texts:
                                paragraphs.append("".join(texts))
                    if paragraphs:
                        return "\n".join(paragraphs)
        except Exception:
            pass
        return ""

    if b"\x00" in file_bytes[:65_536]:
        return ""
    decoded = file_bytes.decode("utf-8", errors="replace").strip()
    if decoded.count("\ufffd") > max(3, int(len(decoded) * 0.05)):
        return ""
    return decoded


def chunk_text(
    text: str,
    *,
    default_title: str = "Document",
    max_chars: int = 850,
    overlap_chars: int = 100,
) -> list[tuple[str, str]]:
    """Split document text into section-aware overlapping chunks."""
    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return [(default_title, default_title)]

    lines = normalized.split("\n")
    sections: list[tuple[str, list[str]]] = []
    current_section = default_title
    current_buf: list[str] = []

    for line in lines:
        stripped = line.strip()
        heading_match = re.match(r"^#{1,4}\s+(.+)$", stripped)
        if heading_match:
            if current_buf:
                sections.append((current_section, current_buf))
                current_buf = []
            current_section = heading_match.group(1).strip()[:200]
        else:
            current_buf.append(line)

    if current_buf:
        sections.append((current_section, current_buf))

    chunks: list[tuple[str, str]] = []
    for section_title, sec_lines in sections:
        section_body = "\n".join(sec_lines).strip()
        if not section_body:
            continue
        if len(section_body) <= max_chars:
            chunks.append((section_title, section_body))
            continue

        start = 0
        while start < len(section_body):
            end = min(len(section_body), start + max_chars)
            piece = section_body[start:end].strip()
            if piece:
                chunks.append((section_title, piece))
            if end >= len(section_body):
                break
            start = max(start + 1, end - overlap_chars)

    return chunks or [(default_title, normalized[:max_chars])]


def index_document_chunks(
    db: Session,
    *,
    doc: KnowledgeDocument,
    text_content: str,
) -> int:
    """Idempotently chunk and embed a KnowledgeDocument into pgvector `knowledge_chunks`."""
    obsidian = parse_obsidian_markdown(text_content)
    clean_body = obsidian["body_text"] or text_content
    fm = obsidian["frontmatter"]
    chunks = chunk_text(clean_body, default_title=doc.title)
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))

    for idx, (section_title, chunk_content) in enumerate(chunks):
        embedding = compute_text_embedding(f"{doc.title}\n{section_title}\n{chunk_content}")
        meta_json = {
            "source_type": doc.source_type,
            "original_filename": doc.original_filename,
            "tags": obsidian["tags"],
            "wikilinks": obsidian["wikilinks"],
        }
        if fm.get("department"):
            meta_json["department"] = str(fm["department"])[:80]
        if fm.get("effective_date"):
            meta_json["effective_date"] = str(fm["effective_date"])[:40]
        if fm.get("workflow"):
            meta_json["workflow"] = str(fm["workflow"])[:80]

        chunk_row = KnowledgeChunk(
            tenant_id=doc.tenant_id,
            document_id=doc.id,
            rental_id=doc.rental_id,
            chunk_index=idx,
            section_title=section_title,
            min_role_access=doc.min_role_access,
            content=chunk_content,
            token_count=max(1, len(chunk_content.split())),
            embedding=embedding,
            metadata_json=meta_json,
        )
        db.add(chunk_row)

    doc.chunk_count = len(chunks)
    doc.status = "indexed"
    db.flush()

    from agents.framework.optimizer import tenant_response_cache

    tenant_response_cache.invalidate_tenant(doc.tenant_id)
    return len(chunks)


def semantic_search_knowledge(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    rental_id: Optional[uuid.UUID],
    actor_role: str,
    query: str,
    top_k: int = 5,
    min_similarity: float = 0.05,
    source_types: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Query tenant-isolated pgvector knowledge chunks respecting document RBAC roles & Obsidian tags/wikilinks."""
    query_vec = compute_text_embedding(query)
    actor_rank = ROLE_RANK.get(actor_role, 1)
    query_terms = {
        tok
        for tok in re.findall(r"[a-z0-9_-]{3,}", (query or "").lower())
        if tok not in {"what", "when", "where", "which", "how", "does", "the", "for", "and", "our"}
    }

    stmt = (
        select(
            KnowledgeChunk,
            KnowledgeDocument,
            KnowledgeChunk.embedding.cosine_distance(query_vec).label("distance"),
        )
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(
            KnowledgeChunk.tenant_id == tenant_id,
            KnowledgeDocument.tenant_id == tenant_id,
            KnowledgeDocument.status == "indexed",
        )
    )
    if rental_id is not None:
        stmt = stmt.where(KnowledgeChunk.rental_id == rental_id)
    if source_types:
        stmt = stmt.where(KnowledgeDocument.source_type.in_(source_types))

    stmt = stmt.order_by("distance").limit(max(top_k * 4, 15))
    rows = db.execute(stmt).all()

    scored: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    wikilink_targets: set[str] = set()

    for chunk, doc, distance in rows:
        required_rank = ROLE_RANK.get(chunk.min_role_access or doc.min_role_access, 1)
        if actor_rank < required_rank:
            continue

        meta = dict(chunk.metadata_json or {})
        tags = [str(t).lower() for t in (meta.get("tags") or [])]
        vec_sim = max(0.0, 1.0 - float(distance))
        chunk_lower = f"{doc.title} {chunk.section_title or ''} {chunk.content}".lower()
        lexical_hits = sum(1 for term in query_terms if term in chunk_lower)
        tag_hits = sum(1 for term in query_terms if term in tags)
        lexical_bonus = min(0.35, lexical_hits * 0.12) + min(0.18, tag_hits * 0.09) if query_terms else 0.0
        combined_score = vec_sim + lexical_bonus

        if combined_score < min_similarity and lexical_hits == 0 and tag_hits == 0:
            continue

        cid_str = str(chunk.id)
        seen_chunk_ids.add(cid_str)
        for wl in meta.get("wikilinks") or []:
            wikilink_targets.add(str(wl).strip().lower())

        scored.append(
            {
                "chunk_id": cid_str,
                "document_id": str(doc.id),
                "document_title": doc.title,
                "original_filename": doc.original_filename,
                "source_type": doc.source_type,
                "section_title": chunk.section_title or "Overview",
                "chunk_index": chunk.chunk_index,
                "similarity": round(min(1.0, combined_score), 4),
                "vector_similarity": round(vec_sim, 4),
                "tags": tags,
                "wikilinks": list(meta.get("wikilinks") or []),
                "excerpt": chunk.content,
            }
        )

    # 1-hop Obsidian [[wikilink]] retrieval across tenant RBAC-allowed documents if room remains
    if wikilink_targets and len(scored) < top_k:
        linked_docs = db.execute(
            select(KnowledgeChunk, KnowledgeDocument)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(
                KnowledgeChunk.tenant_id == tenant_id,
                KnowledgeDocument.tenant_id == tenant_id,
                KnowledgeDocument.status == "indexed",
            )
            .limit(40)
        ).all()
        for l_chunk, l_doc in linked_docs:
            if len(scored) >= top_k:
                break
            req_rank = ROLE_RANK.get(l_chunk.min_role_access or l_doc.min_role_access, 1)
            if actor_rank < req_rank or str(l_chunk.id) in seen_chunk_ids:
                continue
            title_low = l_doc.title.strip().lower()
            stem_low = l_doc.original_filename.rsplit(".", 1)[0].strip().lower()
            if any(wt == title_low or wt == stem_low or wt in title_low for wt in wikilink_targets):
                seen_chunk_ids.add(str(l_chunk.id))
                scored.append(
                    {
                        "chunk_id": str(l_chunk.id),
                        "document_id": str(l_doc.id),
                        "document_title": l_doc.title,
                        "original_filename": l_doc.original_filename,
                        "source_type": l_doc.source_type,
                        "section_title": l_chunk.section_title or "Linked Policy",
                        "chunk_index": l_chunk.chunk_index,
                        "similarity": 0.45,
                        "vector_similarity": 0.0,
                        "tags": list((l_chunk.metadata_json or {}).get("tags") or []),
                        "wikilinks": [],
                        "linked_via_wikilink": True,
                        "excerpt": l_chunk.content,
                    }
                )

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:top_k]
