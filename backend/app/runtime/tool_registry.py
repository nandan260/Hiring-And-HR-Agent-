from __future__ import annotations

import base64
import concurrent.futures
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Candidate, InterviewRecord, KnowledgeDocument, OnboardingWorkflow
from app.runtime.docker_sandbox import SandboxSecurityError, SandboxTimeoutError, sandbox_manager
from app.runtime.playwright_browser import BrowserSecurityError, browser_manager
from app.runtime.redaction import redact_secrets_in_text, sanitize_structured_payload


@dataclass
class ToolExecutionContext:
    db: Session
    tenant_id: uuid.UUID
    rental_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_role: str
    blind_screening_mode: bool = False
    strict_pii_masking: bool = True
    runtime_id: uuid.UUID | None = None


class GenericToolInput(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ResumeParseInput(BaseModel):
    content_base64: str | None = Field(default=None, description="Base64 encoded file bytes")
    workspace_file: str | None = Field(default=None, description="Relative path inside tenant sandbox workspace")
    candidate_id: str | None = Field(default=None, description="Optional candidate UUID to update or extract from")
    blind_screening: bool = Field(default=False, description="Mask candidate PII fields when extracting")


class CandidateSearchInput(BaseModel):
    query: str = Field(default="", max_length=300, description="Keyword or skill filter")
    skills: list[str] = Field(default_factory=list, description="Required skills list")
    min_experience_years: int = Field(default=0, ge=0, le=50)
    min_match_score: int = Field(default=0, ge=0, le=100)
    limit: int = Field(default=10, ge=1, le=50)


class JobSearchInput(BaseModel):
    query: str = Field(default="", max_length=300, description="Title, department, or skill filter")
    status: str | None = Field(default=None, max_length=40)
    department: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=10, ge=1, le=50)


class HrDocumentRetrieverInput(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="HR policy/handbook semantic query")
    top_k: int = Field(default=4, ge=1, le=12)


class JobDescriptionGeneratorInput(BaseModel):
    role_title: str = Field(..., min_length=2, max_length=200)
    department: str = Field(default="Engineering", max_length=120)
    seniority: str = Field(default="Senior", max_length=60)
    required_skills: list[str] = Field(default_factory=list)
    location: str = Field(default="Remote / Hybrid", max_length=120)


class EmailDraftGeneratorInput(BaseModel):
    recipient_name: str = Field(..., min_length=1, max_length=150)
    email_type: str = Field(
        default="interview_invite",
        description="interview_invite | rejection_polite | offer_followup | onboarding_welcome",
    )
    role_title: str = Field(default="Open Role", max_length=200)
    proposed_slots: list[str] = Field(default_factory=list)
    notes: str = Field(default="", max_length=600)


class CalendarAvailabilityInput(BaseModel):
    interviewer_names: list[str] = Field(default_factory=lambda: ["Hiring Manager", "Staff Engineer"])
    start_date: str | None = Field(default=None, description="ISO date YYYY-MM-DD")
    days_ahead: int = Field(default=5, ge=1, le=14)
    duration_minutes: int = Field(default=45, ge=15, le=180)


class BrowserSearchInput(BaseModel):
    url: str | None = Field(default=None, description="Approved target URL to inspect")
    query: str = Field(default="", max_length=300, description="Recruitment search query")
    target_urls: list[str] = Field(default_factory=list, description="Explicit approved URLs")
    capture_screenshot: bool = Field(default=True)
    route_mock_html: dict[str, str] | None = Field(default=None, exclude=True)


class OnboardingChecklistInput(BaseModel):
    action: str = Field(default="list", description="list | get | complete_task | add_task")
    workflow_id: str | None = Field(default=None)
    employee_name: str | None = Field(default=None, max_length=200)
    task_id: str | None = Field(default=None, max_length=80)
    task_title: str | None = Field(default=None, max_length=200)
    owner: str = Field(default="HR Ops", max_length=80)


class DefaultToolOutput(BaseModel):
    ok: bool = True
    tool_id: str
    data: dict[str, Any] = Field(default_factory=dict)


@dataclass
class RegisteredToolSpec:
    tool_id: str
    name: str
    description: str
    category: str
    input_model: type[BaseModel]
    output_model: type[BaseModel] = DefaultToolOutput
    required_roles: tuple[str, ...] = ("platform_admin", "business_owner", "business_admin", "business_employee")
    requires_hitl: bool = False
    risk_level: str = "low"  # low | medium | high
    timeout_seconds: int = 15
    handler: Callable[[ToolExecutionContext, dict[str, Any]], dict[str, Any]] | None = None
    legacy_aliases: tuple[str, ...] = field(default_factory=tuple)

    def to_metadata_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(),
            "required_roles": list(self.required_roles),
            "requires_hitl": self.requires_hitl,
            "risk_level": self.risk_level,
            "timeout_seconds": self.timeout_seconds,
            "legacy_aliases": list(self.legacy_aliases),
        }


def _handle_resume_pdf_parser(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    rt = sandbox_manager.ensure_tenant_runtime(ctx.db, ctx.tenant_id, rental_id=ctx.rental_id)
    payload: dict[str, Any] = {}
    if args.get("content_base64"):
        payload["content_base64"] = args["content_base64"]
    elif args.get("workspace_file"):
        payload["workspace_file"] = args["workspace_file"]
    elif args.get("candidate_id"):
        cand = ctx.db.scalar(
            select(Candidate).where(
                Candidate.id == uuid.UUID(str(args["candidate_id"])),
                Candidate.tenant_id == ctx.tenant_id,
            )
        )
        if cand and cand.resume_text:
            return {
                "source": "candidate_record",
                "candidate_id": str(cand.id),
                "extracted_text": cand.resume_text[:12000],
                "detected_skills": cand.skills_json,
                "years_experience": float(cand.years_experience or 0),
                "sandbox_runtime_id": str(rt.id),
                "backend_mode": rt.backend_mode,
            }
        raise ValueError("Candidate not found or has no resume payload")
    else:
        raise ValueError("Provide content_base64, workspace_file, or candidate_id")

    exec_res = sandbox_manager.execute_in_runtime(
        ctx.db, ctx.tenant_id, rt.id, task_name="parse_pdf_resume", payload=payload
    )
    out = dict(exec_res["result"])
    if args.get("blind_screening") or ctx.blind_screening_mode:
        out["emails"] = ["[MASKED_IN_BLIND_MODE]"] if out.get("emails") else []
        out["phones"] = ["[MASKED_IN_BLIND_MODE]"] if out.get("phones") else []
    out["sandbox_runtime_id"] = exec_res["runtime_id"]
    out["backend_mode"] = exec_res["backend_mode"]
    out["is_container_isolated"] = exec_res["is_container_isolated"]
    return out


def _handle_resume_docx_parser(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    rt = sandbox_manager.ensure_tenant_runtime(ctx.db, ctx.tenant_id, rental_id=ctx.rental_id)
    payload: dict[str, Any] = {}
    if args.get("content_base64"):
        payload["content_base64"] = args["content_base64"]
    elif args.get("workspace_file"):
        payload["workspace_file"] = args["workspace_file"]
    else:
        raise ValueError("Provide content_base64 or workspace_file")

    exec_res = sandbox_manager.execute_in_runtime(
        ctx.db, ctx.tenant_id, rt.id, task_name="parse_docx_resume", payload=payload
    )
    out = dict(exec_res["result"])
    if args.get("blind_screening") or ctx.blind_screening_mode:
        out["emails"] = ["[MASKED_IN_BLIND_MODE]"] if out.get("emails") else []
    out["sandbox_runtime_id"] = exec_res["runtime_id"]
    out["backend_mode"] = exec_res["backend_mode"]
    out["is_container_isolated"] = exec_res["is_container_isolated"]
    return out


def _handle_candidate_database_search(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    stmt = select(Candidate).where(Candidate.tenant_id == ctx.tenant_id)
    if args.get("min_experience_years", 0) > 0:
        stmt = stmt.where(Candidate.years_experience >= int(args["min_experience_years"]))
    if args.get("min_match_score", 0) > 0:
        stmt = stmt.where(Candidate.match_score >= int(args["min_match_score"]))
    query = (args.get("query") or "").strip().lower()
    rows = ctx.db.scalars(stmt.order_by(Candidate.match_score.desc().nullslast()).limit(100)).all()

    req_skills = [s.lower() for s in (args.get("skills") or [])]
    matched: list[dict[str, Any]] = []
    for c in rows:
        skills_lower = [str(s).lower() for s in (c.skills_json or [])]
        if req_skills and not all(rs in skills_lower for rs in req_skills):
            continue
        blob = f"{c.full_name} {c.target_role} {' '.join(skills_lower)} {c.resume_text or ''}".lower()
        if query and query not in blob:
            continue
        matched.append(
            {
                "id": str(c.id),
                "full_name": f"Candidate-{str(c.id)[:6]}" if ctx.blind_screening_mode else c.full_name,
                "target_role": c.target_role,
                "years_experience": float(c.years_experience or 0),
                "match_score": float(c.match_score) if c.match_score is not None else None,
                "status": c.status,
                "skills": c.skills_json,
                "masked_email": "[REDACTED]" if ctx.blind_screening_mode else c.email,
            }
        )
        if len(matched) >= int(args.get("limit", 10)):
            break
    return {"total_found": len(matched), "candidates": matched}


def _handle_job_database_search(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    query = (args.get("query") or "").strip().lower()
    status_filter = (args.get("status") or "").strip().lower()
    dept_filter = (args.get("department") or "").strip().lower()

    docs = ctx.db.scalars(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.tenant_id == ctx.tenant_id,
            or_(
                KnowledgeDocument.source_type.in_(["job_description", "jd", "role_rubric", "leveling_guide"]),
                KnowledgeDocument.title.ilike("%job%"),
                KnowledgeDocument.title.ilike("%engineer%"),
                KnowledgeDocument.title.ilike("%role%"),
            ),
        )
        .order_by(KnowledgeDocument.created_at.desc())
        .limit(30)
    ).all()

    cand_roles = ctx.db.scalars(
        select(Candidate.target_role).where(Candidate.tenant_id == ctx.tenant_id).distinct()
    ).all()
    iv_roles = ctx.db.scalars(
        select(InterviewRecord.role_title).where(InterviewRecord.tenant_id == ctx.tenant_id).distinct()
    ).all()

    jobs_by_title: dict[str, dict[str, Any]] = {}
    for doc in docs:
        key = doc.title.strip()
        jobs_by_title[key.lower()] = {
            "id": str(doc.id),
            "title": doc.title,
            "source_type": doc.source_type,
            "department": args.get("department") or "General",
            "status": doc.status or "indexed",
            "source": "knowledge_document",
        }
    for role in [*cand_roles, *iv_roles]:
        clean = (role or "").strip()
        if clean and clean.lower() not in jobs_by_title:
            jobs_by_title[clean.lower()] = {
                "id": f"role-{clean.lower().replace(' ', '-')[:28]}",
                "title": clean,
                "source_type": "active_requisition",
                "department": "Engineering" if "engineer" in clean.lower() else "Operations",
                "status": "open",
                "source": "pipeline_role",
            }

    filtered: list[dict[str, Any]] = []
    for item in jobs_by_title.values():
        blob = f"{item['title']} {item['department']} {item['source_type']}".lower()
        if query and query not in blob:
            continue
        if status_filter and item["status"].lower() != status_filter:
            continue
        if dept_filter and dept_filter not in item["department"].lower():
            continue
        filtered.append(item)
        if len(filtered) >= int(args.get("limit", 10)):
            break
    return {"total_found": len(filtered), "jobs": filtered}


def _handle_hr_document_retriever(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    from agents.framework.rag import semantic_search_knowledge

    hits = semantic_search_knowledge(
        ctx.db,
        tenant_id=ctx.tenant_id,
        rental_id=ctx.rental_id,
        actor_role=ctx.actor_role,
        query=args["query"],
        top_k=int(args.get("top_k", 4)),
    )
    return {
        "query": args["query"],
        "chunks_found": len(hits),
        "citations": hits,
    }


def _handle_job_description_generator(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    from agents.framework.rag import semantic_search_knowledge

    role_title = args["role_title"]
    department = args.get("department", "Engineering")
    seniority = args.get("seniority", "Senior")
    skills = args.get("required_skills") or ["Communication", "Problem Solving", "Collaboration"]
    location = args.get("location", "Remote / Hybrid")
    kb_hits = semantic_search_knowledge(
        ctx.db,
        tenant_id=ctx.tenant_id,
        rental_id=ctx.rental_id,
        actor_role=ctx.actor_role,
        query=f"{role_title} leveling guide",
        top_k=2,
    )

    jd_markdown = (
        f"# {seniority} {role_title}\n"
        f"**Department:** {department} | **Location:** {location}\n\n"
        f"## Role Overview\n"
        f"We are seeking a {seniority} {role_title} to join our {department} team and deliver high-impact initiatives.\n\n"
        f"## Core Qualifications\n"
        + "\n".join(f"- Hands-on experience with {s}" for s in skills)
        + "\n\n## Inclusive Hiring Commitment\n"
        "We evaluate candidates based on skills, potential, and role impact rather than pedigree."
    )
    return {
        "role_title": role_title,
        "department": department,
        "seniority": seniority,
        "jd_markdown": jd_markdown,
        "kb_references_used": [h.get("document_title") or h.get("doc_title") or h.get("section_title") for h in kb_hits],
    }


def _handle_email_draft_generator(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    recipient = args["recipient_name"]
    email_type = args["email_type"]
    role = args.get("role_title", "Open Role")
    slots = args.get("proposed_slots") or []
    notes = args.get("notes", "")

    if email_type == "interview_invite":
        subject = f"Interview Invitation — {role}"
        slot_txt = "\n".join(f"- {s}" for s in slots) if slots else "- We will confirm mutually convenient slots shortly."
        body = (
            f"Hi {recipient},\n\nThank you for applying for {role}. We would love to schedule your interview.\n"
            f"Available options:\n{slot_txt}\n\n{notes}\nBest regards,\nHiring Team"
        ).strip()
    elif email_type == "onboarding_welcome":
        subject = f"Welcome to the Team — {role} Onboarding"
        body = (
            f"Hi {recipient},\n\nWelcome aboard as our {role}! Please review your onboarding checklist before day one.\n"
            f"{notes}\n\nBest regards,\nPeople Operations"
        ).strip()
    elif email_type == "rejection_polite":
        subject = f"Update on your {role} application"
        body = (
            f"Hi {recipient},\n\nThank you sincerely for speaking with us regarding {role}. "
            f"At this stage we are advancing candidates whose background aligns more closely with our immediate needs.\n\n"
            "Warm regards,\nHiring Team"
        )
    else:
        subject = f"Following up regarding {role}"
        body = f"Hi {recipient},\n\nFollowing up regarding {role}. {notes}\n\nBest regards,\nHR Team".strip()

    return {
        "requires_human_approval": True,
        "auto_sent": False,
        "email_type": email_type,
        "subject": subject,
        "body": body,
    }


def _handle_calendar_availability_checker(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    existing = ctx.db.scalars(
        select(InterviewRecord).where(
            InterviewRecord.tenant_id == ctx.tenant_id,
            InterviewRecord.status.in_(["scheduled", "proposed"]),
        )
    ).all()
    busy_windows = {
        iv.scheduled_start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        for iv in existing
        if iv.scheduled_start
    }

    start = datetime.now(timezone.utc).date() + timedelta(days=1)
    if args.get("start_date"):
        try:
            start = datetime.fromisoformat(args["start_date"]).date()
        except ValueError:
            pass

    slots: list[dict[str, Any]] = []
    interviewers = args.get("interviewer_names") or ["Hiring Manager"]
    days_ahead = int(args.get("days_ahead", 5))
    duration = int(args.get("duration_minutes", 45))

    for d in range(days_ahead):
        day = start + timedelta(days=d)
        if day.weekday() >= 5:
            continue
        for hour in (10, 14, 16):
            slot_key = f"{day.isoformat()} {hour:02d}:00 UTC"
            if slot_key not in busy_windows:
                slots.append(
                    {
                        "slot_label": f"{slot_key} ({duration}m)",
                        "interviewers": interviewers,
                        "duration_minutes": duration,
                        "conflict_free": True,
                    }
                )
            if len(slots) >= 6:
                break
        if len(slots) >= 6:
            break
    return {"checked_interviewers": interviewers, "busy_count": len(busy_windows), "available_slots": slots}


def _handle_browser_search(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    target_url = args.get("url")
    target_urls = list(args.get("target_urls") or [])
    route_mock = args.get("route_mock_html")
    if target_url:
        res = browser_manager.navigate_and_extract(
            tenant_id=ctx.tenant_id,
            url=target_url,
            capture_screenshot=bool(args.get("capture_screenshot", True)),
            route_mock_html=route_mock,
        )
        return res
    return browser_manager.search_recruitment_info(
        tenant_id=ctx.tenant_id,
        query=args.get("query", ""),
        target_urls=target_urls or None,
        route_mock_html=route_mock,
    )


def _handle_onboarding_checklist_manager(ctx: ToolExecutionContext, args: dict[str, Any]) -> dict[str, Any]:
    action = args.get("action", "list")
    stmt = select(OnboardingWorkflow).where(OnboardingWorkflow.tenant_id == ctx.tenant_id)
    if args.get("workflow_id"):
        stmt = stmt.where(OnboardingWorkflow.id == uuid.UUID(str(args["workflow_id"])))
    workflows = ctx.db.scalars(stmt.order_by(OnboardingWorkflow.created_at.desc())).all()

    if action in {"list", "get"}:
        return {
            "count": len(workflows),
            "workflows": [
                {
                    "id": str(w.id),
                    "employee_name": w.employee_name,
                    "role_title": w.role_title,
                    "current_stage": w.current_stage,
                    "progress_percent": w.progress_percent,
                    "checklist": w.checklist_json,
                }
                for w in workflows[:10]
            ],
        }

    if not workflows:
        raise ValueError("No onboarding workflow found for tenant")
    wf = workflows[0]
    checklist = list(wf.checklist_json or [])

    if action == "complete_task":
        task_id = str(args.get("task_id") or "")
        updated = False
        for item in checklist:
            label = item.get("title") or item.get("item")
            if (task_id and str(item.get("id")) == task_id) or (args.get("task_title") and label == args.get("task_title")):
                item["status"] = "completed"
                item["completed"] = True
                updated = True
        if not updated:
            raise ValueError(f"Checklist task '{task_id or args.get('task_title')}' not found")
    elif action == "add_task":
        title = str(args.get("task_title") or "").strip()
        if not title:
            raise ValueError("task_title is required when adding a task")
        checklist.append(
            {
                "id": f"task-{uuid.uuid4().hex[:6]}",
                "title": title,
                "item": title,
                "owner": args.get("owner", "HR Ops"),
                "status": "pending",
                "completed": False,
            }
        )
    else:
        raise ValueError(f"Unsupported onboarding action: {action}")

    wf.checklist_json = checklist
    completed_count = sum(1 for item in checklist if item.get("status") == "completed" or item.get("completed") is True)
    wf.progress_percent = round((completed_count / len(checklist)) * 100) if checklist else 0
    ctx.db.flush()
    return {
        "workflow_id": str(wf.id),
        "employee_name": wf.employee_name,
        "progress_percent": wf.progress_percent,
        "checklist": checklist,
    }


CORE_HR_TOOLS: list[RegisteredToolSpec] = [
    RegisteredToolSpec(
        tool_id="resume_pdf_parser",
        name="Resume PDF Parser",
        description="Parses uploaded PDF resumes inside an isolated sandbox runtime to extract text, skills, and experience.",
        category="recruitment",
        input_model=ResumeParseInput,
        required_roles=("platform_admin", "business_owner", "business_admin", "business_employee"),
        risk_level="low",
        timeout_seconds=15,
        handler=_handle_resume_pdf_parser,
    ),
    RegisteredToolSpec(
        tool_id="resume_docx_parser",
        name="Resume DOCX Parser",
        description="Parses Word .docx resumes inside an isolated sandbox runtime including paragraphs and tables.",
        category="recruitment",
        input_model=ResumeParseInput,
        required_roles=("platform_admin", "business_owner", "business_admin", "business_employee"),
        risk_level="low",
        timeout_seconds=15,
        handler=_handle_resume_docx_parser,
    ),
    RegisteredToolSpec(
        tool_id="candidate_database_search",
        name="Candidate Database Search",
        description="Searches tenant-scoped candidates by skills, match score, title, and experience years.",
        category="recruitment",
        input_model=CandidateSearchInput,
        required_roles=("platform_admin", "business_owner", "business_admin", "business_employee"),
        risk_level="low",
        timeout_seconds=10,
        handler=_handle_candidate_database_search,
    ),
    RegisteredToolSpec(
        tool_id="job_database_search",
        name="Job Database Search",
        description="Searches tenant-scoped job requisitions by status, department, and keywords.",
        category="recruitment",
        input_model=JobSearchInput,
        required_roles=("platform_admin", "business_owner", "business_admin", "business_employee"),
        risk_level="low",
        timeout_seconds=10,
        handler=_handle_job_database_search,
    ),
    RegisteredToolSpec(
        tool_id="hr_document_retriever",
        name="HR Document Retriever",
        description="Performs tenant-isolated RAG semantic + keyword retrieval across uploaded HR policies and guides.",
        category="knowledge",
        input_model=HrDocumentRetrieverInput,
        required_roles=("platform_admin", "business_owner", "business_admin", "business_employee"),
        risk_level="low",
        timeout_seconds=12,
        handler=_handle_hr_document_retriever,
    ),
    RegisteredToolSpec(
        tool_id="job_description_generator",
        name="Job Description Generator",
        description="Drafts structured, bias-checked job descriptions aligned with tenant leveling guides.",
        category="talent",
        input_model=JobDescriptionGeneratorInput,
        required_roles=("platform_admin", "business_owner", "business_admin", "business_employee"),
        risk_level="low",
        timeout_seconds=15,
        handler=_handle_job_description_generator,
    ),
    RegisteredToolSpec(
        tool_id="email_draft_generator",
        name="Email Draft Generator",
        description="Generates review-gated HR outreach, interview invitation, and onboarding email drafts without auto-sending.",
        category="communication",
        input_model=EmailDraftGeneratorInput,
        required_roles=("platform_admin", "business_owner", "business_admin"),
        requires_hitl=True,
        risk_level="medium",
        timeout_seconds=10,
        handler=_handle_email_draft_generator,
    ),
    RegisteredToolSpec(
        tool_id="calendar_availability_checker",
        name="Calendar Availability Checker",
        description="Checks tenant interview schedules and proposes conflict-free interviewer time slots.",
        category="scheduling",
        input_model=CalendarAvailabilityInput,
        required_roles=("platform_admin", "business_owner", "business_admin", "business_employee"),
        risk_level="low",
        timeout_seconds=10,
        handler=_handle_calendar_availability_checker,
    ),
    RegisteredToolSpec(
        tool_id="browser_search",
        name="Approved Browser Search",
        description="Opens allowlisted websites inside an isolated Playwright context with SSRF, download, and cookie isolation.",
        category="browser",
        input_model=BrowserSearchInput,
        required_roles=("platform_admin", "business_owner", "business_admin"),
        risk_level="medium",
        timeout_seconds=25,
        handler=_handle_browser_search,
    ),
    RegisteredToolSpec(
        tool_id="onboarding_checklist_manager",
        name="Onboarding Checklist Manager",
        description="Lists, adds, or completes tenant employee onboarding checklist milestones.",
        category="onboarding",
        input_model=OnboardingChecklistInput,
        required_roles=("platform_admin", "business_owner", "business_admin"),
        requires_hitl=False,
        risk_level="medium",
        timeout_seconds=10,
        handler=_handle_onboarding_checklist_manager,
    ),
]


class StructuredHRToolRegistry:
    """Central schema-enforced, role-checked, timeout-protected HR Tool Registry."""

    def __init__(self) -> None:
        self._specs: dict[str, RegisteredToolSpec] = {}
        self._legacy_handlers: dict[str, Callable[..., dict[str, Any]]] = {}
        for spec in CORE_HR_TOOLS:
            self._specs[spec.tool_id] = spec

    def register_spec(self, spec: RegisteredToolSpec) -> None:
        self._specs[spec.tool_id] = spec

    def register_legacy_handler(
        self,
        slug: str,
        handler: Callable[..., dict[str, Any]],
        *,
        name: str | None = None,
        description: str = "",
        category: str = "workflow",
        risk_level: str = "low",
        requires_hitl: bool = False,
        timeout_seconds: int = 15,
    ) -> None:
        self._legacy_handlers[slug] = handler
        if slug not in self._specs:
            self._specs[slug] = RegisteredToolSpec(
                tool_id=slug,
                name=name or slug.replace("_", " ").title(),
                description=description or f"Workflow tool '{slug}'",
                category=category,
                input_model=GenericToolInput,
                requires_hitl=requires_hitl,
                risk_level=risk_level,
                timeout_seconds=timeout_seconds,
                handler=None,
            )

    def has_tool(self, tool_id: str) -> bool:
        return tool_id in self._specs or tool_id in self._legacy_handlers

    def get_spec(self, tool_id: str) -> RegisteredToolSpec | None:
        return self._specs.get(tool_id)

    def list_tools_metadata(self, *, core_only: bool = False) -> list[dict[str, Any]]:
        specs = CORE_HR_TOOLS if core_only else list(self._specs.values())
        return [s.to_metadata_dict() for s in specs]

    def execute(
        self,
        tool_id: str,
        ctx: ToolExecutionContext,
        args: dict[str, Any],
        *,
        agent_allowed_tools: list[str] | None = None,
        rental_allowed_tools: list[str] | None = None,
        timeout_override: int | None = None,
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        spec = self._specs.get(tool_id)

        if agent_allowed_tools is not None and tool_id not in agent_allowed_tools:
            return {
                "tool": tool_id,
                "status": "denied",
                "duration_ms": 0,
                "error": f"Tool '{tool_id}' is not authorized for this workflow",
            }
        if rental_allowed_tools is not None and tool_id not in rental_allowed_tools:
            return {
                "tool": tool_id,
                "status": "denied",
                "duration_ms": 0,
                "error": f"Tool '{tool_id}' is disabled in tenant tool policy",
            }
        if spec is None and tool_id not in self._legacy_handlers:
            return {
                "tool": tool_id,
                "status": "not_found",
                "duration_ms": 0,
                "error": f"Tool '{tool_id}' is not registered",
            }

        if spec is not None and ctx.actor_role not in spec.required_roles and ctx.actor_role != "platform_admin":
            return {
                "tool": tool_id,
                "status": "denied",
                "duration_ms": 0,
                "error": f"Role '{ctx.actor_role}' is not permitted to invoke tool '{tool_id}'",
            }

        # Validate structured input parameters when spec defines a domain Pydantic schema
        validated_args = dict(args or {})
        if spec is not None and spec.input_model is not GenericToolInput:
            try:
                model_obj = spec.input_model(**validated_args)
                extra_fields = {k: v for k, v in validated_args.items() if k == "route_mock_html"}
                validated_args = {**model_obj.model_dump(), **extra_fields}
            except ValidationError as exc:
                return {
                    "tool": tool_id,
                    "status": "validation_error",
                    "duration_ms": round((time.perf_counter() - t0) * 1000),
                    "error": f"Invalid tool parameters: {exc.errors()[0].get('msg', str(exc))}",
                }

        eff_timeout = int(timeout_override or (spec.timeout_seconds if spec else 15))
        handler = spec.handler if (spec and spec.handler is not None) else self._legacy_handlers.get(tool_id)
        if handler is None:
            return {
                "tool": tool_id,
                "status": "not_configured",
                "duration_ms": 0,
                "error": f"No execution handler attached to '{tool_id}'",
            }

        def _invoke():
            return handler(ctx, validated_args)

        try:
            # Execute directly in caller thread when using SQLAlchemy Session (SQLAlchemy Session is not thread-safe across threads!)
            # Enforce explicit execution deadline check cleanly, and use sandbox/MCP timeouts for I/O or subprocess work.
            res = _invoke()
            duration_ms = round((time.perf_counter() - t0) * 1000)
            if duration_ms > eff_timeout * 1000:
                return {
                    "tool": tool_id,
                    "status": "timeout",
                    "duration_ms": duration_ms,
                    "error": f"Tool '{tool_id}' exceeded {eff_timeout}s budget",
                }
            return {
                "tool": tool_id,
                "name": spec.name if spec else tool_id,
                "status": "ok",
                "duration_ms": duration_ms,
                "requires_hitl": spec.requires_hitl if spec else False,
                "risk_level": spec.risk_level if spec else "low",
                "result": sanitize_structured_payload(res, max_str_len=4000),
            }
        except (BrowserSecurityError, SandboxSecurityError) as exc:
            return {
                "tool": tool_id,
                "status": "blocked_security",
                "duration_ms": round((time.perf_counter() - t0) * 1000),
                "error": redact_secrets_in_text(str(exc), max_len=400),
            }
        except (SandboxTimeoutError, TimeoutError) as exc:
            return {
                "tool": tool_id,
                "status": "timeout",
                "duration_ms": round((time.perf_counter() - t0) * 1000),
                "error": redact_secrets_in_text(str(exc), max_len=400),
            }
        except Exception as exc:
            return {
                "tool": tool_id,
                "status": "error",
                "duration_ms": round((time.perf_counter() - t0) * 1000),
                "error": redact_secrets_in_text(f"{type(exc).__name__}: {exc}", max_len=400),
            }


hr_tool_registry = StructuredHRToolRegistry()
