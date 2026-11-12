"""Lightweight PostgreSQL-backed HR knowledge & skill graph within the tenant RLS boundary."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Candidate, InterviewRecord, KnowledgeChunk, KnowledgeDocument

# Curated bidirectional HR & engineering skill equivalence clusters for 1-hop semantic graph matching.
SKILL_EQUIVALENTS: dict[str, set[str]] = {
    "python": {"fastapi", "django", "drf", "flask", "pydantic", "pytest", "asyncio"},
    "fastapi": {"python", "pydantic", "starlette", "openapi", "rest api"},
    "django": {"python", "drf", "django rest framework"},
    "postgresql": {"postgres", "pgvector", "sql", "sqlalchemy", "relational database"},
    "sql": {"postgresql", "mysql", "sqlite", "t-sql"},
    "react": {"reactjs", "next.js", "nextjs", "typescript", "javascript", "frontend"},
    "typescript": {"javascript", "react", "node.js", "nodejs"},
    "kubernetes": {"k8s", "helm", "eks", "gke", "aks", "docker", "containers"},
    "docker": {"containers", "kubernetes", "docker-compose", "oci"},
    "aws": {"amazon web services", "ec2", "s3", "ecs", "eks", "lambda", "iam"},
    "machine learning": {"ml", "pytorch", "tensorflow", "scikit-learn", "nlp", "llm", "langgraph"},
    "llm": {"langchain", "langgraph", "rag", "pgvector", "prompt engineering", "openai", "gemini"},
    "hr operations": {"onboarding", "hrms", "payroll", "employee relations", "hr compliance"},
    "talent acquisition": {"recruiting", "sourcing", "interviewing", "candidate screening", "ats"},
}


def _build_reverse_equivalents() -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {k: set(v) for k, v in SKILL_EQUIVALENTS.items()}
    for canonical, aliases in SKILL_EQUIVALENTS.items():
        for alias in aliases:
            merged.setdefault(alias, set()).add(canonical)
    return merged


_GRAPH_NEIGHBORS = _build_reverse_equivalents()


def expand_skill_equivalents(skills: list[str]) -> dict[str, set[str]]:
    """Expand each required skill with its 1-hop graph neighbors."""
    expanded: dict[str, set[str]] = {}
    for skill in skills:
        norm = (skill or "").strip().lower()
        if not norm:
            continue
        expanded[skill] = {norm} | _GRAPH_NEIGHBORS.get(norm, set())
    return expanded


def compute_graph_skill_matches(
    required_skills: list[str],
    candidate_skills_or_text: list[str] | str,
) -> dict[str, Any]:
    """
    Evaluate direct and 1-hop graph-equivalent skill coverage without sacrificing explainability.
    Direct matches carry full credit; 1-hop graph neighbors (e.g. FastAPI -> Python) surface transparently.
    """
    if isinstance(candidate_skills_or_text, list):
        cand_lower = {str(s).strip().lower() for s in candidate_skills_or_text if s}
        cand_blob = " ".join(cand_lower)
    else:
        cand_blob = (candidate_skills_or_text or "").lower()
        cand_lower = set()

    direct_matches: list[str] = []
    graph_matches: list[dict[str, str]] = []
    missing_skills: list[str] = []

    for req in required_skills:
        norm = req.strip().lower()
        if not norm:
            continue
        if norm in cand_lower or norm in cand_blob:
            direct_matches.append(req)
            continue
        neighbors = _GRAPH_NEIGHBORS.get(norm, set())
        hit_neighbor = next((n for n in sorted(neighbors) if n in cand_lower or n in cand_blob), None)
        if hit_neighbor:
            graph_matches.append({"required": req, "via_neighbor": hit_neighbor})
        else:
            missing_skills.append(req)

    effective_score = len(direct_matches) + (0.75 * len(graph_matches))
    ratio = (effective_score / len(required_skills)) if required_skills else 0.85
    return {
        "direct_matches": direct_matches,
        "graph_matches": graph_matches,
        "missing_skills": missing_skills,
        "effective_ratio": min(1.0, round(ratio, 4)),
    }


def build_tenant_hr_graph(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    include_pii: bool = False,
    limit_docs: int = 30,
    limit_candidates: int = 30,
) -> dict[str, Any]:
    """Build an explainable node/edge graph linking tenant KB documents, Obsidian tags/wikilinks, candidates, skills, and interviews."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def add_node(node_id: str, node_type: str, label: str, **meta: Any) -> None:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "type": node_type, "label": label, **meta}

    docs = (
        db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.status == "indexed")
            .order_by(KnowledgeDocument.created_at.desc())
            .limit(limit_docs)
        )
        .scalars()
        .all()
    )
    chunks = (
        db.execute(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.tenant_id == tenant_id, KnowledgeChunk.chunk_index == 0)
            .limit(limit_docs)
        )
        .scalars()
        .all()
    )
    chunk_by_doc = {str(ch.document_id): ch for ch in chunks}
    doc_title_map: dict[str, str] = {}

    for doc in docs:
        doc_nid = f"doc:{doc.id}"
        doc_title_map[doc.title.strip().lower()] = doc_nid
        doc_title_map[doc.original_filename.rsplit(".", 1)[0].strip().lower()] = doc_nid
        add_node(doc_nid, "document", doc.title, source_type=doc.source_type, min_role_access=doc.min_role_access)

        first_chunk = chunk_by_doc.get(str(doc.id))
        meta = dict(first_chunk.metadata_json or {}) if first_chunk else {}
        for tag in meta.get("tags") or []:
            t_norm = str(tag).strip().lower()
            if not t_norm:
                continue
            tag_nid = f"tag:{t_norm}"
            add_node(tag_nid, "tag", f"#{t_norm}")
            edges.append({"source": doc_nid, "target": tag_nid, "relation": "TAGGED_WITH"})
        if meta.get("workflow"):
            wf = str(meta["workflow"])
            wf_nid = f"workflow:{wf}"
            add_node(wf_nid, "workflow", wf)
            edges.append({"source": doc_nid, "target": wf_nid, "relation": "GUIDES_WORKFLOW"})

    # Add [[wikilink]] edges between tenant documents
    for doc in docs:
        first_chunk = chunk_by_doc.get(str(doc.id))
        meta = dict(first_chunk.metadata_json or {}) if first_chunk else {}
        doc_nid = f"doc:{doc.id}"
        for wl in meta.get("wikilinks") or []:
            wl_norm = str(wl).strip().lower()
            target_nid = doc_title_map.get(wl_norm) or f"note:{wl_norm}"
            if target_nid.startswith("note:"):
                add_node(target_nid, "referenced_note", wl)
            edges.append({"source": doc_nid, "target": target_nid, "relation": "WIKILINK_TO"})

    candidates = (
        db.execute(
            select(Candidate)
            .where(Candidate.tenant_id == tenant_id)
            .order_by(Candidate.created_at.desc())
            .limit(limit_candidates)
        )
        .scalars()
        .all()
    )
    for idx, cand in enumerate(candidates):
        cand_nid = f"candidate:{cand.id}"
        label = cand.full_name if include_pii else f"Candidate #{idx + 1}"
        add_node(cand_nid, "candidate", label, target_role=cand.target_role, status=cand.status)
        for skill in list(cand.skills_json or [])[:12]:
            s_norm = str(skill).strip().lower()
            if not s_norm:
                continue
            sk_nid = f"skill:{s_norm}"
            add_node(sk_nid, "skill", str(skill).strip())
            edges.append({"source": cand_nid, "target": sk_nid, "relation": "HAS_SKILL"})

    interviews = (
        db.execute(
            select(InterviewRecord)
            .where(InterviewRecord.tenant_id == tenant_id)
            .order_by(InterviewRecord.created_at.desc())
            .limit(20)
        )
        .scalars()
        .all()
    )
    for iv in interviews:
        iv_nid = f"interview:{iv.id}"
        add_node(iv_nid, "interview", f"Interview ({iv.status})", stage=iv.interview_stage)
        if iv.candidate_id:
            edges.append({"source": f"candidate:{iv.candidate_id}", "target": iv_nid, "relation": "SCHEDULED_FOR"})

    return {
        "tenant_id": str(tenant_id),
        "pii_included": include_pii,
        "summary": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "documents": len(docs),
            "candidates": len(candidates),
            "interviews": len(interviews),
        },
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def get_compact_graph_context(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    query: str = "",
    required_skills: Optional[list[str]] = None,
    include_pii: bool = False,
    max_chars: int = 650,
) -> str:
    """Return a concise, low-token summary of graph skill clusters and document links for LLM grounding."""
    parts: list[str] = []
    if required_skills:
        expanded = expand_skill_equivalents(required_skills[:5])
        hints = [f"{sk}~({', '.join(sorted(neis - {sk.lower()})[:3])})" for sk, neis in expanded.items() if len(neis) > 1]
        if hints:
            parts.append("Skill graph links: " + "; ".join(hints))

    graph = build_tenant_hr_graph(db, tenant_id, include_pii=include_pii, limit_docs=10, limit_candidates=10)
    wikilink_edges = [e for e in graph["edges"] if e["relation"] == "WIKILINK_TO"][:4]
    if wikilink_edges:
        node_lookup = {n["id"]: n["label"] for n in graph["nodes"]}
        links_txt = ", ".join(
            f"{node_lookup.get(e['source'], e['source'])} -> {node_lookup.get(e['target'], e['target'])}"
            for e in wikilink_edges
        )
        parts.append(f"Policy links: {links_txt}")

    joined = " | ".join(parts)
    return joined[:max_chars]
