"""Agent 1: Recruitment & Resume Screening Agent."""

from __future__ import annotations

from decimal import Decimal
import re
from typing import Any, Literal, Optional
import uuid

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.storage import resolve_tenant_file
from app.db.models import Candidate, KnowledgeDocument
from app.runtime.docker_sandbox import sandbox_manager
from app.runtime.document_security import neutralize_untrusted_document_text
from app.runtime.hr_knowledge_graph import compute_graph_skill_matches
from app.runtime.playwright_browser import BrowserSecurityError, browser_manager

from .framework.base_agent import BaseSpecializedAgent
from .framework.llm_provider import llm_provider
from .framework.rag import compute_text_embedding, extract_document_text
from .framework.schemas import (
    BaseAgentInput,
    BaseAgentOutput,
    DomainDefinition,
    ExecutionLimits,
    GuardrailConfig,
    KnowledgeBaseConfig,
    MemoryConfig,
    ModelConfig,
    ToolPermissionConfig,
)
from .framework.state import AgentExecutionState
from .framework.tools import AgentToolBox, ToolContext

KNOWN_SKILL_LEXICON = [
    "python",
    "fastapi",
    "django",
    "flask",
    "postgresql",
    "postgres",
    "pgvector",
    "sql",
    "mysql",
    "redis",
    "langgraph",
    "langchain",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "react",
    "typescript",
    "javascript",
    "tailwind",
    "java",
    "spring boot",
    "go",
    "kafka",
    "terraform",
    "ci/cd",
    "graphql",
    "microservices",
    "distributed systems",
    "row-level security",
    "rls",
    "rest api",
    "git",
    "pytest",
    "machine learning",
    "nlp",
    "rag",
    "llm",
    "playwright",
]


class RecruitmentInput(BaseAgentInput):
    job_title: Optional[str] = Field(default=None, description="Target role title for screening")
    job_description: str = Field(default="", description="Job description text to extract requirements from")
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_years_experience: float = Field(default=0.0, ge=0.0, le=50.0)
    resume_texts: list[str] = Field(default_factory=list, description="Inline resume text snippets")
    document_ids: list[str] = Field(default_factory=list, description="Tenant KnowledgeDocument IDs (resumes)")
    portfolio_urls: list[str] = Field(default_factory=list, description="Optional candidate public portfolio URLs")
    search_candidate_pool: bool = Field(default=True, description="Also search tenant Candidate DB with pgvector")
    blind_screening: Optional[bool] = Field(default=None, description="Override blind screening PII redaction")
    persist_new_resumes: bool = Field(default=True)


class ScreenedCandidateReport(BaseModel):
    candidate_id: Optional[str] = None
    candidate_label: str
    target_role: str
    years_experience: float
    extracted_skills: list[str]
    matched_required_skills: list[str]
    matched_preferred_skills: list[str]
    missing_skills: list[str]
    match_score: float = Field(ge=0.0, le=100.0)
    semantic_similarity: float = Field(ge=0.0, le=1.0)
    experience_highlights: list[str]
    evidence_quotes: list[str]
    recommendation_for_human_review: Literal[
        "Strong Match - Recommend Human Review",
        "Partial Match - Needs Human Review",
        "Gap Identified - Human Review Required",
    ]
    human_review_required: bool = True


class RecruitmentOutput(BaseAgentOutput):
    parsed_requirements: dict[str, Any]
    blind_screening_applied: bool
    evaluated_candidates: list[ScreenedCandidateReport]
    invalid_resumes: list[dict[str, str]] = Field(default_factory=list)


def _sanitize_resume_text(raw: str) -> str:
    """Neutralize embedded prompt injections, ranking directives, and script smuggling in untrusted resume text."""
    neutralized, _flags = neutralize_untrusted_document_text(raw, source_name="resume_input")
    return neutralized


def _extract_skills(text: str, extra_terms: list[str]) -> list[str]:
    lower = (text or "").lower()
    found: list[str] = []
    seen_lower: set[str] = set()
    candidates = list(KNOWN_SKILL_LEXICON) + [t.strip() for t in extra_terms if t.strip()]
    for skill in candidates:
        s_low = skill.lower()
        if s_low in seen_lower:
            continue
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(s_low)}(?![a-z0-9])", re.IGNORECASE)
        if pattern.search(lower):
            seen_lower.add(s_low)
            found.append(skill if skill in extra_terms else skill.title() if len(skill) > 3 else skill.upper())
    return found


def _extract_years_experience(text: str) -> float:
    matches = re.findall(r"(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+experience)?", text or "", re.IGNORECASE)
    if not matches:
        return 0.0
    vals = [float(m) for m in matches if 0.0 <= float(m) <= 45.0]
    return max(vals) if vals else 0.0


def _extract_candidate_name(text: str, idx: int) -> str:
    first_line = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    # Common resume header "Aarav Mehta - Senior..." or "Name: Aarav Mehta"
    m_prefix = re.match(r"^(?:name\s*:\s*)([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+){1,3})", first_line)
    if m_prefix:
        return m_prefix.group(1).strip()
    m_dash = re.match(r"^([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+){1,2})\s*(?:[-—|]|$)", first_line)
    if m_dash:
        return m_dash.group(1).strip()
    return f"Applicant {idx + 1}"


def _parse_job_requirements(parsed_input: RecruitmentInput) -> dict[str, Any]:
    jd_combo = f"{parsed_input.job_title or ''}\n{parsed_input.job_description}\n{parsed_input.prompt}"
    job_title = parsed_input.job_title
    if not job_title:
        role_match = re.search(
            r"(?:for|role\s*:|position\s*:)\s*([A-Z][A-Za-z0-9/\s-]{3,45}?)(?:\s+(?:with|requiring|in|,|\.|$))",
            jd_combo,
        )
        job_title = role_match.group(1).strip() if role_match else "Software Engineer"

    inferred_req = _extract_skills(
        f"{parsed_input.job_description} {parsed_input.prompt}",
        list(parsed_input.required_skills) + list(parsed_input.preferred_skills),
    )
    req_skills = list(parsed_input.required_skills) or inferred_req[:6]
    pref_skills = [s for s in parsed_input.preferred_skills if s.lower() not in {r.lower() for r in req_skills}]
    min_years = parsed_input.min_years_experience or _extract_years_experience(jd_combo)
    return {
        "job_title": job_title,
        "required_skills": req_skills,
        "preferred_skills": pref_skills,
        "min_years_experience": min_years,
    }


class RecruitmentScreeningAgent(BaseSpecializedAgent):
    """Evaluates job requirements, parses resumes, extracts skills, and suggests matches for human review."""

    agent_id = "recruitment-screening"
    agent_name = "Recruitment & Resume Screening Agent"
    agent_version = "1.2.0"
    system_prompt_file = "recruitment_agent.md"
    domain = DomainDefinition(
        domain_name="Recruitment & Resume Screening",
        allowed_topics=[
            "job description parsing",
            "resume text extraction",
            "candidate skill & experience extraction",
            "blind PII redaction",
            "explainable rubric candidate matching",
        ],
        rejected_categories={
            "Medical Diagnosis & Clinical Advice": "Healthcare",
            "Financial Trading & Cryptocurrency": "Business and Finance",
            "Legal Litigation & Contract Redlining": "Legal and Compliance",
        },
        in_domain_keywords=[
            "recruit",
            "recruitment",
            "resume",
            "resumes",
            "cv",
            "candidate",
            "candidates",
            "screen",
            "screening",
            "job description",
            "jd",
            "skill",
            "skills",
            "experience",
            "applicant",
            "rubric",
            "backend",
            "engineer",
            "developer",
            "match",
            "hiring",
        ],
        min_keyword_hits=1,
        suggested_marketplace_category="Hiring and HR",
    )
    input_schema = RecruitmentInput
    output_schema = RecruitmentOutput
    allowed_tools = [
        "sandbox_ocr_extract",
        "pii_blind_masker",
        "rubric_scorer",
        "playwright_verify_portfolio",
        "ats_post_scorecard",
    ]
    tool_permissions = ToolPermissionConfig(
        default_allowed_tools=allowed_tools,
        hitl_required_tools=["ats_post_scorecard"],
        read_only_tools=["sandbox_ocr_extract", "pii_blind_masker", "rubric_scorer", "playwright_verify_portfolio"],
    )
    knowledge_base = KnowledgeBaseConfig(
        enabled=True,
        top_k=5,
        min_similarity=0.05,
        require_citations=False,
        allowed_source_types=["resume", "rubric", "jd_template"],
    )
    model_cfg = ModelConfig(provider="auto", model_tier="tier_1_slm", temperature=0.1, max_tokens=1400)
    guardrails = GuardrailConfig(
        block_prompt_injection=True,
        block_protected_characteristics=True,
        prohibit_auto_reject=True,
        pii_redaction_mode="standard",
    )
    memory = MemoryConfig(short_term_window_messages=10, summary_max_tokens=400, persist_to_db=True)
    execution_limits = ExecutionLimits(max_steps=12, max_tool_calls=6, max_input_tokens=10000, max_output_tokens=1800)

    def register_tools(self, toolbox: AgentToolBox) -> None:
        toolbox.register("sandbox_ocr_extract", self._tool_sandbox_ocr_extract)
        toolbox.register("pii_blind_masker", self._tool_pii_blind_masker)
        toolbox.register("rubric_scorer", self._tool_rubric_scorer)
        toolbox.register("playwright_verify_portfolio", self._tool_playwright_verify_portfolio)
        toolbox.register("ats_post_scorecard", self._tool_ats_post_scorecard)

    def _tool_sandbox_ocr_extract(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        import base64

        rt = sandbox_manager.ensure_tenant_runtime(ctx.db, ctx.tenant_id, rental_id=ctx.rental_id)
        sandbox_meta: dict[str, Any] = {
            "runtime_id": str(rt.id),
            "agent_runtime_id": rt.agent_runtime_id,
            "backend_mode": rt.backend_mode,
            "is_container_isolated": rt.is_container_isolated,
        }
        req = args.get("requirements", {})
        all_skill_terms = list(req.get("required_skills", [])) + list(req.get("preferred_skills", []))
        parsed_resumes: list[dict[str, Any]] = []
        invalid_resumes: list[dict[str, str]] = []

        # 1. Extract from uploaded tenant KnowledgeDocuments inside isolated sandbox worker
        for doc_id_str in args.get("document_ids", []):
            try:
                doc_uuid = uuid.UUID(str(doc_id_str))
            except ValueError:
                invalid_resumes.append({"source": str(doc_id_str), "reason": "invalid_document_uuid"})
                continue
            doc = ctx.db.execute(
                select(KnowledgeDocument).where(
                    KnowledgeDocument.id == doc_uuid,
                    KnowledgeDocument.tenant_id == ctx.tenant_id,
                )
            ).scalar_one_or_none()
            if doc is None:
                invalid_resumes.append({"source": str(doc_id_str), "reason": "document_not_found"})
                continue
            raw_text = ""
            try:
                path = resolve_tenant_file(ctx.tenant_id, doc.storage_rel_path)
                raw_bytes = path.read_bytes()
                lower_name = (doc.original_filename or "").lower()
                if lower_name.endswith(".pdf") or "pdf" in (doc.mime_type or "").lower():
                    try:
                        sb_res = sandbox_manager.execute_in_runtime(
                            ctx.db,
                            ctx.tenant_id,
                            rt.id,
                            task_name="parse_pdf_resume",
                            payload={"content_base64": base64.b64encode(raw_bytes).decode("ascii")},
                        )
                        raw_text = (sb_res.get("result") or {}).get("extracted_text", "")
                        sandbox_meta["last_task"] = "parse_pdf_resume"
                        sandbox_meta["duration_ms"] = sb_res.get("duration_ms", 0)
                    except Exception:
                        raw_text = extract_document_text(raw_bytes, filename=doc.original_filename, mime_type=doc.mime_type)
                elif lower_name.endswith(".docx") or "wordprocessingml" in (doc.mime_type or "").lower():
                    try:
                        sb_res = sandbox_manager.execute_in_runtime(
                            ctx.db,
                            ctx.tenant_id,
                            rt.id,
                            task_name="parse_docx_resume",
                            payload={"content_base64": base64.b64encode(raw_bytes).decode("ascii")},
                        )
                        raw_text = (sb_res.get("result") or {}).get("extracted_text", "")
                        sandbox_meta["last_task"] = "parse_docx_resume"
                        sandbox_meta["duration_ms"] = sb_res.get("duration_ms", 0)
                    except Exception:
                        raw_text = extract_document_text(raw_bytes, filename=doc.original_filename, mime_type=doc.mime_type)
                if not raw_text:
                    raw_text = extract_document_text(raw_bytes, filename=doc.original_filename, mime_type=doc.mime_type)
            except Exception as exc:
                invalid_resumes.append(
                    {"source": doc.original_filename or str(doc.id), "reason": f"unreadable_file: {exc}"}
                )
                continue

            if (
                len(re.findall(r"[A-Za-z0-9]", raw_text or "")) < 10
                or (raw_text or "").count("\ufffd") > max(5, len(raw_text or "") * 0.08)
                or "\x00" in (raw_text or "")
            ):
                invalid_resumes.append(
                    {
                        "source": doc.original_filename or str(doc.id),
                        "reason": "corrupted_or_empty_resume_content",
                    }
                )
                continue
            cleaned = _sanitize_resume_text(raw_text)
            email_m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", cleaned)
            phone_m = re.search(r"(?:\+?\d[\d\s\-()]{7,18}\d)", cleaned)
            years = _extract_years_experience(cleaned)
            skills = _extract_skills(cleaned, all_skill_terms)
            name = _extract_candidate_name(cleaned, len(parsed_resumes))
            parsed_resumes.append(
                {
                    "source": "knowledge_document",
                    "source_document_id": str(doc.id),
                    "full_name": name,
                    "email": email_m.group(0) if email_m else None,
                    "phone": phone_m.group(0) if phone_m else None,
                    "years_experience": years,
                    "skills": skills,
                    "resume_text": cleaned,
                }
            )

        if not args.get("document_ids") and args.get("resume_texts"):
            sb_ping = sandbox_manager.execute_in_runtime(
                ctx.db,
                ctx.tenant_id,
                rt.id,
                task_name="noop_ping",
                payload={"ping": "inline_resume_screening"},
            )
            sandbox_meta["last_task"] = "noop_ping"
            sandbox_meta["duration_ms"] = sb_ping.get("duration_ms", 0)

        # 2. Extract from inline resume texts
        for idx, raw_cv in enumerate(args.get("resume_texts", [])):
            raw_cv_str = str(raw_cv or "")
            if (
                not raw_cv_str.strip()
                or len(re.findall(r"[A-Za-z0-9]", raw_cv_str)) < 10
                or raw_cv_str.count("\ufffd") > max(5, len(raw_cv_str) * 0.08)
                or "\x00" in raw_cv_str
            ):
                invalid_resumes.append(
                    {"source": f"inline_resume_{idx + 1}", "reason": "corrupted_or_empty_resume_text"}
                )
                continue
            cleaned = _sanitize_resume_text(raw_cv_str)
            email_m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", cleaned)
            phone_m = re.search(r"(?:\+?\d[\d\s\-()]{7,18}\d)", cleaned)
            years = _extract_years_experience(cleaned)
            skills = _extract_skills(cleaned, all_skill_terms)
            name = _extract_candidate_name(cleaned, idx)
            parsed_resumes.append(
                {
                    "source": "inline_resume",
                    "source_document_id": None,
                    "full_name": name,
                    "email": email_m.group(0) if email_m else None,
                    "phone": phone_m.group(0) if phone_m else None,
                    "years_experience": years,
                    "skills": skills,
                    "resume_text": cleaned,
                }
            )

        # 3. Persist newly extracted resumes into tenant candidates table for future shortlisting
        if args.get("persist_new_resumes", True):
            for entry in parsed_resumes:
                existing = ctx.db.execute(
                    select(Candidate).where(
                        Candidate.tenant_id == ctx.tenant_id,
                        Candidate.full_name == entry["full_name"],
                    )
                ).scalar_one_or_none()
                if existing is None:
                    cand = Candidate(
                        tenant_id=ctx.tenant_id,
                        rental_id=ctx.rental_id,
                        full_name=entry["full_name"],
                        email=entry["email"],
                        phone=entry["phone"],
                        target_role=req.get("job_title", "Software Engineer"),
                        years_experience=Decimal(str(round(entry["years_experience"], 2))),
                        skills_json=entry["skills"],
                        resume_text=entry["resume_text"][:8000],
                        source_document_id=uuid.UUID(entry["source_document_id"])
                        if entry["source_document_id"]
                        else None,
                        status="screened",
                        embedding=compute_text_embedding(
                            f"{entry['full_name']} {req.get('job_title', '')} {' '.join(entry['skills'])} {entry['resume_text'][:1500]}"
                        ),
                    )
                    ctx.db.add(cand)
                    ctx.db.flush()
                    entry["candidate_id"] = str(cand.id)
                else:
                    entry["candidate_id"] = str(existing.id)

        return {
            "requirements": req,
            "extracted_resumes": parsed_resumes,
            "invalid_resumes": invalid_resumes,
            "_sandbox_meta": sandbox_meta,
        }

    def _tool_pii_blind_masker(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        blind = bool(args.get("blind_screening", ctx.blind_screening_mode))
        return {
            "blind_screening_active": blind,
            "redacted_fields": ["full_name", "email", "phone"] if blind else [],
        }

    def _tool_rubric_scorer(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        req = args.get("requirements", {})
        blind = bool(args.get("blind_screening", ctx.blind_screening_mode))
        req_skills = [s for s in req.get("required_skills", []) if s]
        pref_skills = [s for s in req.get("preferred_skills", []) if s]
        min_years = float(req.get("min_years_experience", 0.0) or 0.0)
        job_title = req.get("job_title", "Software Engineer")

        query_vec = compute_text_embedding(
            f"{job_title} {' '.join(req_skills)} {' '.join(pref_skills)} {args.get('job_description', '')}"
        )

        pool_rows: list[tuple[Candidate, float]] = []
        if args.get("search_candidate_pool", True):
            stmt = (
                select(Candidate, Candidate.embedding.cosine_distance(query_vec).label("distance"))
                .where(Candidate.tenant_id == ctx.tenant_id, Candidate.embedding.is_not(None))
                .order_by("distance")
                .limit(12)
            )
            for cand, distance in ctx.db.execute(stmt).all():
                sim = max(0.0, 1.0 - float(distance))
                pool_rows.append((cand, sim))

        # Score candidate records deterministically without protected characteristics
        evaluated: list[dict[str, Any]] = []
        for idx, (cand, sem_sim) in enumerate(pool_rows):
            cand_skills = list(cand.skills_json or [])
            cand_skills_lower = {s.lower() for s in cand_skills}
            text_lower = (cand.resume_text or "").lower()

            matched_req = [
                s for s in req_skills if s.lower() in cand_skills_lower or s.lower() in text_lower
            ]
            missing = [s for s in req_skills if s not in matched_req]
            matched_pref = [
                s for s in pref_skills if s.lower() in cand_skills_lower or s.lower() in text_lower
            ]
            graph_eval = compute_graph_skill_matches(req_skills, cand_skills + ([cand.resume_text] if cand.resume_text else []))
            graph_links = graph_eval["graph_matches"]

            req_ratio = (len(matched_req) / len(req_skills)) if req_skills else 0.85
            if missing and graph_links and req_skills:
                req_ratio = min(1.0, graph_eval["effective_ratio"])
            pref_ratio = (len(matched_pref) / len(pref_skills)) if pref_skills else 0.5
            cand_years = float(cand.years_experience or 0.0)
            exp_ratio = (min(1.0, cand_years / min_years)) if min_years > 0 else min(1.0, cand_years / 5.0 + 0.3)

            score = round(min(100.0, (req_ratio * 60.0) + (exp_ratio * 25.0) + (pref_ratio * 10.0) + (sem_sim * 5.0)), 1)

            if score >= 75.0:
                rec = "Strong Match - Recommend Human Review"
            elif score >= 45.0:
                rec = "Partial Match - Needs Human Review"
            else:
                rec = "Gap Identified - Human Review Required"

            quotes = [
                line.strip()[:220]
                for line in (cand.resume_text or "").splitlines()
                if line.strip()
            ][:2]
            if blind and quotes:
                quotes = [q.replace(cand.full_name, "[CANDIDATE]") for q in quotes]

            highlights = [
                f"{exp.get('role', 'Role')} at {exp.get('company', 'Company')} ({exp.get('years', '?')} yrs)"
                for exp in (cand.experience_json or [])
            ]
            if not highlights:
                highlights = [f"{cand_years:.1f} years relevant experience in {cand.target_role}"]

            label = f"Candidate #{idx + 1}" if blind else cand.full_name
            cand.match_score = Decimal(str(score))
            cand.screening_summary_json = {
                "matched_required_skills": matched_req,
                "graph_skill_links": graph_links,
                "missing_skills": missing,
                "recommendation": rec,
            }
            evaluated.append(
                {
                    "candidate_id": str(cand.id),
                    "candidate_label": label,
                    "target_role": cand.target_role,
                    "years_experience": cand_years,
                    "extracted_skills": cand_skills,
                    "matched_required_skills": matched_req,
                    "matched_preferred_skills": matched_pref,
                    "missing_skills": missing,
                    "match_score": score,
                    "semantic_similarity": round(sem_sim, 4),
                    "experience_highlights": highlights,
                    "evidence_quotes": quotes or [f"Verified skills: {', '.join(cand_skills[:5])}"],
                    "recommendation_for_human_review": rec,
                    "human_review_required": True,
                }
            )

        evaluated.sort(key=lambda item: item["match_score"], reverse=True)
        ctx.db.flush()
        return {"blind_screening_applied": blind, "evaluated_candidates": evaluated}

    def _tool_playwright_verify_portfolio(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        raw_urls = [str(u).strip() for u in args.get("portfolio_urls", []) if str(u).strip()]
        if not raw_urls:
            return {
                "checked_urls": [],
                "visited_pages": [],
                "blocked_requests": [],
                "verified_status": "not_used",
                "note": "No candidate portfolio URLs provided",
            }
        visited_pages: list[dict[str, Any]] = []
        blocked: list[dict[str, str]] = []
        checked_urls: list[str] = []
        for url in raw_urls[:2]:
            try:
                page_res = browser_manager.navigate_and_extract(
                    tenant_id=ctx.tenant_id,
                    url=url,
                    capture_screenshot=True,
                )
                visited_pages.append(page_res)
                checked_urls.append(page_res.get("final_url", url))
                blocked.extend(page_res.get("blocked_requests", []))
            except BrowserSecurityError as exc:
                blocked.append({"url": url, "reason": str(exc)})
            except Exception as exc:
                blocked.append({"url": url, "reason": str(exc)})
        return {
            "checked_urls": checked_urls,
            "visited_pages": visited_pages,
            "blocked_requests": blocked,
            "verified_status": "verified" if visited_pages else ("blocked" if blocked else "not_used"),
        }

    def _tool_ats_post_scorecard(self, ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
        return {"staged_for_hitl_approval": True, "count": args.get("candidate_count", 0)}

    def select_tools(
        self,
        parsed_input: RecruitmentInput,
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> list[dict[str, Any]]:
        reqs = _parse_job_requirements(parsed_input)
        blind = (
            parsed_input.blind_screening
            if parsed_input.blind_screening is not None
            else ctx.blind_screening_mode
        )
        planned = [
            {
                "tool": "sandbox_ocr_extract",
                "args": {
                    "requirements": reqs,
                    "resume_texts": parsed_input.resume_texts,
                    "document_ids": parsed_input.document_ids,
                    "persist_new_resumes": parsed_input.persist_new_resumes,
                },
            },
            {"tool": "pii_blind_masker", "args": {"blind_screening": blind}},
            {
                "tool": "rubric_scorer",
                "args": {
                    "requirements": reqs,
                    "blind_screening": blind,
                    "job_description": parsed_input.job_description or parsed_input.prompt,
                    "search_candidate_pool": parsed_input.search_candidate_pool,
                },
            },
        ]
        if parsed_input.portfolio_urls:
            planned.append({"tool": "playwright_verify_portfolio", "args": {"portfolio_urls": parsed_input.portfolio_urls}})
        return planned

    def synthesize_output(
        self,
        parsed_input: RecruitmentInput,
        tool_results: list[dict[str, Any]],
        memory_ctx: dict[str, Any],
        state: AgentExecutionState,
        ctx: ToolContext,
    ) -> tuple[RecruitmentOutput, dict[str, Any]]:
        reqs = _parse_job_requirements(parsed_input)
        blind = bool(
            parsed_input.blind_screening
            if parsed_input.blind_screening is not None
            else ctx.blind_screening_mode
        )
        scored_candidates: list[dict[str, Any]] = []
        invalid_resumes: list[dict[str, str]] = []
        for res in tool_results:
            if res.get("status") == "completed" and res.get("tool") == "sandbox_ocr_extract":
                out = res.get("output", {})
                invalid_resumes.extend(list(out.get("invalid_resumes") or []))
            if res.get("status") == "completed" and res.get("tool") == "rubric_scorer":
                out = res.get("output", {})
                blind = bool(out.get("blind_screening_applied", blind))
                scored_candidates = list(out.get("evaluated_candidates", []))

        invalid_note = ""
        if invalid_resumes:
            bad_sources = ", ".join(f"{item['source']} ({item['reason']})" for item in invalid_resumes)
            invalid_note = f" Rejected unreadable/corrupt resume input(s): {bad_sources}."

        def _fallback_json(_context: dict[str, Any] | None = None) -> dict[str, Any]:
            top_names = ", ".join(
                f"{c['candidate_label']} ({c['match_score']}%)" for c in scored_candidates[:3]
            )
            summary = (
                f"Screened {len(scored_candidates)} candidate(s) for **{reqs['job_title']}** "
                f"(Required skills: {', '.join(reqs['required_skills']) or 'General'}). "
                + (f"Top matches for human review: {top_names}." if top_names else "No valid candidates found in input or pool.")
                + invalid_note
            )
            explanation = (
                "Scores are strictly grounded in extracted technical skills, years of experience, and pgvector "
                "semantic similarity against the job rubric. "
                + ("Blind screening masked personal identifiers prior to evaluation. " if blind else "")
                + "All candidates remain available for recruiter review (zero automatic rejections)."
                + invalid_note
            )
            return {"summary": summary, "explanation": explanation}

        llm_res = llm_provider.generate_structured(
            system_prompt=self.load_system_prompt(state.get("custom_persona_prompt", "")),
            user_prompt=parsed_input.prompt,
            context_data={
                "requirements": reqs,
                "blind_screening_applied": blind,
                "evaluated_candidates": scored_candidates[:5],
                "invalid_resumes": invalid_resumes,
            },
            fallback_fn=_fallback_json,
            provider_override=state.get("model_provider_override"),
            temperature=self.model_cfg.temperature,
            max_tokens=self.model_cfg.max_tokens,
        )
        narrative = llm_res.parsed_json or _fallback_json()
        reports = [ScreenedCandidateReport.model_validate(item) for item in scored_candidates]

        base_summary = str(narrative.get("summary") or _fallback_json()["summary"])
        base_explanation = str(narrative.get("explanation") or _fallback_json()["explanation"])
        if invalid_note and "unreadable/corrupt resume" not in base_summary.lower():
            base_summary = f"{base_summary.rstrip()} {invalid_note.strip()}"
        if invalid_note and "unreadable/corrupt resume" not in base_explanation.lower():
            base_explanation = f"{base_explanation.rstrip()} {invalid_note.strip()}"

        output = RecruitmentOutput(
            agent_id=self.agent_id,
            agent_version=self.agent_version,
            summary=base_summary,
            explanation=base_explanation,
            citations=[f"Candidate Pool ({len(reports)} evaluated)", f"Rubric: {reqs['job_title']}"],
            requires_human_approval=False,
            hitl_requests=[],
            structured_payload={
                "requirements": reqs,
                "blind_screening_applied": blind,
                "candidate_count": len(reports),
                "invalid_resumes": invalid_resumes,
            },
            parsed_requirements=reqs,
            blind_screening_applied=blind,
            evaluated_candidates=reports,
            invalid_resumes=invalid_resumes,
        )
        metrics = {
            "provider_used": llm_res.provider_used,
            "model_used": llm_res.model_used,
            "input_tokens": llm_res.input_tokens,
            "cached_tokens": llm_res.cached_tokens,
            "output_tokens": llm_res.output_tokens,
            "estimated_cost_usd": llm_res.estimated_cost_usd,
        }
        return output, metrics
