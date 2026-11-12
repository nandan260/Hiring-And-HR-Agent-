"""API endpoints for HR agent specs, LangGraph execution, HITL approvals, interviews, candidates, and onboarding."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.registry import agent_registry

from ...core.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_tenant_db,
    require_roles,
)
from ...db.models import (
    AgentCatalog,
    AgentRental,
    Candidate,
    HitlApproval,
    InterviewRecord,
    OnboardingWorkflow,
)
from ...services.audit import record_audit

router = APIRouter(tags=["HR Agents & HITL"])


class AgentExecuteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    structured_input: dict[str, Any] = Field(default_factory=dict)
    attachments: list[str] = Field(default_factory=list)
    conversation_id: Optional[uuid.UUID] = None
    model_provider_override: Optional[str] = None


class AgentExecuteResponse(BaseModel):
    execution_status: str
    classifier_result: str
    agent_id: str
    agent_version: str
    execution_log_id: Optional[str] = None
    final_response_text: str
    structured_output: dict[str, Any] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    hitl_requests: list[dict[str, Any]] = Field(default_factory=list)
    trace_steps: list[dict[str, Any]] = Field(default_factory=list)
    llm_provider_used: str = "deterministic"
    model_used: str = "deterministic"
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    suggested_category: Optional[str] = None
    rejection_reason: Optional[str] = None


class HitlResolveRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    resolution_note: Optional[str] = Field(default=None, max_length=1000)


class HitlApprovalResponse(BaseModel):
    id: uuid.UUID
    rental_id: uuid.UUID
    conversation_id: Optional[uuid.UUID]
    agent_slug: str
    action_type: str
    title: str
    summary: str
    payload_json: dict[str, Any]
    status: str
    resolution_note: Optional[str]
    resolved_at: Optional[datetime]
    created_at: datetime


@router.get("/agents/specs")
def list_agent_architecture_specs() -> list[dict[str, Any]]:
    """Return full declarative specifications (schemas, tools, guardrails, memory, limits) for all 7 HR agents."""
    return agent_registry.list_specs()


@router.post("/rentals/{rental_id}/execute", response_model=AgentExecuteResponse)
def execute_rented_agent(
    rental_id: uuid.UUID,
    payload: AgentExecuteRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> AgentExecuteResponse:
    rental = db.scalars(
        select(AgentRental).where(
            AgentRental.id == rental_id,
            AgentRental.tenant_id == principal.tenant_id,
        )
    ).first()
    if rental is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rented agent not found for this tenant")
    if rental.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent rental is currently '{rental.status}'. Activate or resume the rental before executing.",
        )

    catalog = db.get(AgentCatalog, rental.agent_id)
    agent_slug = catalog.slug if catalog else "recruitment-screening"

    state = agent_registry.execute(
        agent_slug=agent_slug,
        db=db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        user_input=payload.prompt,
        rental_id=rental.id,
        conversation_id=payload.conversation_id,
        structured_input=payload.structured_input,
        attachments=payload.attachments,
        model_provider_override=payload.model_provider_override,
        persist_telemetry=True,
    )
    db.commit()

    if state.get("classifier_result") == "blocked_permission":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=state.get("rejection_reason") or "Permission denied for your workspace role.",
        )
    if state.get("classifier_result") == "blocked_quota":
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=state.get("rejection_reason") or "Monthly token quota exceeded.",
        )

    return AgentExecuteResponse(
        execution_status=state.get("execution_status", "completed"),
        classifier_result=state.get("classifier_result", "in_domain"),
        agent_id=state.get("selected_agent_id", agent_slug),
        agent_version=state.get("selected_agent_version", "1.0.0"),
        execution_log_id=state.get("execution_log_id"),
        final_response_text=state.get("final_response_text", ""),
        structured_output=dict(state.get("validated_output") or {}),
        citations=list(state.get("citations") or []),
        charts=list(state.get("charts") or []),
        hitl_requests=list(state.get("hitl_requests") or []),
        trace_steps=[dict(s) for s in (state.get("trace_steps") or [])],
        llm_provider_used=state.get("llm_provider_used", "deterministic"),
        model_used=state.get("model_used", "deterministic"),
        input_tokens=int(state.get("input_tokens", 0)),
        cached_tokens=int(state.get("cached_tokens", 0)),
        output_tokens=int(state.get("output_tokens", 0)),
        latency_ms=int(state.get("latency_ms", 0)),
        suggested_category=state.get("suggested_category"),
        rejection_reason=state.get("rejection_reason"),
    )


@router.get("/hitl/approvals", response_model=list[HitlApprovalResponse])
def list_hitl_approvals(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    rental_id: Optional[uuid.UUID] = Query(default=None),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[HitlApprovalResponse]:
    stmt = select(HitlApproval).where(HitlApproval.tenant_id == principal.tenant_id)
    if status_filter:
        stmt = stmt.where(HitlApproval.status == status_filter)
    if rental_id is not None:
        stmt = stmt.where(HitlApproval.rental_id == rental_id)
    rows = db.scalars(stmt.order_by(HitlApproval.created_at.desc()).limit(50)).all()
    return [
        HitlApprovalResponse(
            id=r.id,
            rental_id=r.rental_id,
            conversation_id=r.conversation_id,
            agent_slug=r.agent_slug,
            action_type=r.action_type,
            title=r.title,
            summary=r.summary,
            payload_json=dict(r.payload_json or {}),
            status=r.status,
            resolution_note=r.resolution_note,
            resolved_at=r.resolved_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/hitl/approvals/{approval_id}/resolve", response_model=HitlApprovalResponse)
def resolve_hitl_approval(
    approval_id: uuid.UUID,
    payload: HitlResolveRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> HitlApprovalResponse:
    row = db.scalars(
        select(HitlApproval).where(
            HitlApproval.id == approval_id,
            HitlApproval.tenant_id == principal.tenant_id,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HITL approval request not found")
    if row.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Request already resolved as '{row.status}'")

    row.status = payload.decision
    row.resolved_by_user_id = principal.user_id
    row.resolution_note = payload.resolution_note
    row.resolved_at = datetime.now(timezone.utc)

    # Apply domain side-effects upon human approval
    if payload.decision == "approved":
        meta = dict(row.payload_json or {})
        if row.action_type == "send_interview_invites" and meta.get("interview_id"):
            try:
                iv = db.scalars(
                    select(InterviewRecord).where(
                        InterviewRecord.id == uuid.UUID(str(meta["interview_id"])),
                        InterviewRecord.tenant_id == principal.tenant_id,
                    )
                ).first()
                if iv is not None:
                    iv.status = "scheduled"
            except ValueError:
                pass
        elif row.action_type in {"it_provisioning_request", "team_allocation"} and meta.get("workflow_id"):
            try:
                wf = db.scalars(
                    select(OnboardingWorkflow).where(
                        OnboardingWorkflow.id == uuid.UUID(str(meta["workflow_id"])),
                        OnboardingWorkflow.tenant_id == principal.tenant_id,
                    )
                ).first()
                if wf is not None:
                    if row.action_type == "it_provisioning_request":
                        it_data = dict(wf.it_provisioning_json or {})
                        it_data["scim_status"] = "provisioned"
                        it_data["ticket_status"] = "submitted"
                        wf.it_provisioning_json = it_data
                    elif row.action_type == "team_allocation":
                        team_data = dict(wf.team_allocation_json or {})
                        team_data["status"] = "confirmed"
                        wf.team_allocation_json = team_data
                    # Update checklist & progress dynamically
                    updated_checklist = []
                    for item in list(wf.checklist_json or []):
                        copy_item = dict(item)
                        if (
                            row.action_type == "it_provisioning_request" and copy_item.get("stage") == "hitl_it_approval"
                        ) or (
                            row.action_type == "team_allocation"
                            and copy_item.get("stage") in {"hitl_team_approval", "training_assignment"}
                        ):
                            copy_item["completed"] = True
                        updated_checklist.append(copy_item)
                    if updated_checklist:
                        wf.checklist_json = updated_checklist
                        done = sum(1 for i in updated_checklist if i.get("completed"))
                        wf.progress_percent = int((done / len(updated_checklist)) * 100)
                        if wf.progress_percent == 100:
                            wf.current_stage = "onboarding_ready"
            except ValueError:
                pass

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=row.rental_id,
        action=f"hitl.approval_{payload.decision}",
        resource_type="hitl_approval",
        resource_id=str(row.id),
        ip_address=principal.ip_address,
        metadata={"action_type": row.action_type, "note": payload.resolution_note},
    )
    db.flush()
    resp = HitlApprovalResponse(
        id=row.id,
        rental_id=row.rental_id,
        conversation_id=row.conversation_id,
        agent_slug=row.agent_slug,
        action_type=row.action_type,
        title=row.title,
        summary=row.summary,
        payload_json=dict(row.payload_json or {}),
        status=row.status,
        resolution_note=row.resolution_note,
        resolved_at=row.resolved_at,
        created_at=row.created_at,
    )
    db.commit()
    return resp


@router.get("/candidates")
def list_tenant_candidates(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Candidate).where(Candidate.tenant_id == principal.tenant_id).order_by(Candidate.created_at.desc()).limit(50)
    ).all()
    return [
        {
            "id": str(c.id),
            "full_name": c.full_name,
            "target_role": c.target_role,
            "years_experience": float(c.years_experience or 0.0),
            "skills": list(c.skills_json or []),
            "match_score": float(c.match_score) if c.match_score is not None else None,
            "status": c.status,
        }
        for c in rows
    ]


@router.get("/interviews")
def list_tenant_interviews(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(InterviewRecord)
        .where(InterviewRecord.tenant_id == principal.tenant_id)
        .order_by(InterviewRecord.scheduled_start.asc())
        .limit(50)
    ).all()
    return [
        {
            "id": str(r.id),
            "candidate_name": r.candidate_name,
            "role_title": r.role_title,
            "interview_stage": r.interview_stage,
            "interviewer_emails": list(r.interviewer_emails or []),
            "scheduled_start": r.scheduled_start.isoformat(),
            "duration_minutes": r.duration_minutes,
            "status": r.status,
            "meeting_link": r.meeting_link,
        }
        for r in rows
    ]


@router.get("/onboarding")
def list_tenant_onboarding_workflows(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(OnboardingWorkflow)
        .where(OnboardingWorkflow.tenant_id == principal.tenant_id)
        .order_by(OnboardingWorkflow.updated_at.desc())
        .limit(50)
    ).all()
    return [
        {
            "id": str(w.id),
            "employee_name": w.employee_name,
            "role_title": w.role_title,
            "department": w.department,
            "current_stage": w.current_stage,
            "progress_percent": w.progress_percent,
            "documents_status": dict(w.documents_status_json or {}),
            "checklist": list(w.checklist_json or []),
            "it_provisioning": dict(w.it_provisioning_json or {}),
            "team_allocation": dict(w.team_allocation_json or {}),
            "training_plan": list(w.training_plan_json or []),
        }
        for w in rows
    ]
