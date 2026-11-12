"""Unified Hiring & HR AI Agent endpoints for HireFlow AI."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents.framework.classifier import (
    HR_WORKFLOW_DISPLAY_NAMES,
    classify_domain_boundary,
    classify_intent_detailed,
)
from agents.framework.optimizer import tenant_response_cache
from agents.framework.rag import (
    export_document_as_obsidian_markdown,
    extract_document_text,
    index_document_chunks,
)
from agents.framework.workflow import WORKFLOW_ALLOWED_ROLES
from agents.registry import agent_registry

from ...core.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_tenant_db,
    require_roles,
)
from ...core.rate_limiter import rate_limiter
from ...core.security import encrypt_secret, mask_secret
from ...core.storage import resolve_tenant_file, save_tenant_upload
from ...db.models import (
    AgentCatalog,
    AgentConfiguration,
    AgentConversation,
    AgentRental,
    AgentSandboxRuntime,
    Candidate,
    ExecutionLog,
    HitlApproval,
    InterviewRecord,
    KnowledgeChunk,
    KnowledgeDocument,
    McpExecutionLog,
    McpServerRecord,
    Message,
    OnboardingWorkflow,
    TokenUsage,
    ToolPermission,
    ToolRegistry,
)
from ...runtime.docker_sandbox import (
    SandboxNotFoundError,
    SandboxSecurityError,
    SandboxTimeoutError,
    sandbox_manager,
)
from ...runtime.document_security import inspect_document_bytes
from ...runtime.hr_knowledge_graph import build_tenant_hr_graph
from ...runtime.mcp_client import McpSecurityError, McpValidationError, mcp_manager
from ...runtime.monitor import monitor_tracker
from ...runtime.playwright_browser import BrowserSecurityError, browser_manager
from ...runtime.tool_registry import ToolExecutionContext, hr_tool_registry
from ...schemas.conversation import ConversationResponse, MessageResponse
from ...services.audit import record_audit
from ...services.hr_workspace import (
    HR_WORKFLOW_SLUGS,
    _compute_config_hash,
    ensure_tenant_hr_workflows,
    get_monthly_token_usage,
)

router = APIRouter(prefix="/hr-agent", tags=["Unified HireFlow HR Agent"])

ROLE_LEVEL = {
    "business_employee": 1,
    "business_admin": 2,
    "business_owner": 3,
    "platform_admin": 4,
}


class UnifiedHrExecuteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=18000)
    workflow_hint: Optional[str] = Field(default=None, max_length=80)
    conversation_id: Optional[uuid.UUID] = None
    structured_input: Optional[dict[str, Any]] = None
    attachments: Optional[list[str]] = None
    model_provider_override: Optional[str] = Field(default=None, max_length=40)
    enable_optimization: Optional[bool] = None


class UnifiedHrExecuteResponse(BaseModel):
    execution_status: str
    classifier_result: str
    routed_workflow: str
    routed_workflow_name: str
    requested_workflow: str
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
    baseline_input_tokens: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    tokens_saved: int = 0
    reduction_percent: float = 0.0
    optimization_enabled: bool = True
    optimization_methods_used: list[str] = Field(default_factory=list)
    guardrail_flags: list[str] = Field(default_factory=list)
    intent_analysis: dict[str, Any] = Field(default_factory=dict)
    clarification_questions: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    rejection_reason: Optional[str] = None


class UnifiedConversationCreateRequest(BaseModel):
    title: str = Field(default="HireFlow HR Assistant Thread", min_length=2, max_length=200)


class UnifiedMessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=18000)
    workflow_hint: Optional[str] = Field(default=None, max_length=80)
    structured_input: Optional[dict[str, Any]] = None
    attachments: Optional[list[str]] = None
    model_provider_override: Optional[str] = Field(default=None, max_length=40)
    enable_optimization: Optional[bool] = None


class UnifiedMessageTurnResponse(BaseModel):
    conversation_id: uuid.UUID
    user_message: MessageResponse
    assistant_message: MessageResponse
    workflow_slug: str
    workflow_name: str
    execution_status: str
    classifier_result: str
    citations: list[str] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    hitl_requests: list[dict[str, Any]] = Field(default_factory=list)
    trace_steps: list[dict[str, Any]] = Field(default_factory=list)
    baseline_input_tokens: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    optimization_methods_used: list[str] = Field(default_factory=list)
    guardrail_flags: list[str] = Field(default_factory=list)
    intent_analysis: dict[str, Any] = Field(default_factory=dict)
    clarification_questions: list[str] = Field(default_factory=list)
    latency_ms: int = 0


class OptimizationCompareRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=12000)
    workflow_hint: Optional[str] = Field(default=None, max_length=80)
    structured_input: Optional[dict[str, Any]] = None
    record_telemetry: bool = False


class UnifiedSettingsUpdateRequest(BaseModel):
    blind_screening_mode: Optional[bool] = None
    strict_pii_masking: Optional[bool] = None
    require_hitl_approval: Optional[bool] = None
    model_routing_tier: Optional[Literal["tier_0_rule", "tier_1_fast", "tier_2_reasoning", "auto_cascade"]] = None
    monthly_token_quota: Optional[int] = Field(default=None, ge=100, le=100_000_000)
    custom_persona_prompt: Optional[str] = Field(default=None, max_length=4000)


class UnifiedToolUpdateRequest(BaseModel):
    is_allowed: bool
    apply_to_all_workflows: bool = True


class UnifiedToolCredentialRequest(BaseModel):
    api_key_or_token: str = Field(..., min_length=4, max_length=2000)
    apply_to_all_workflows: bool = True


def _to_msg_resp(msg: Message) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        classifier_result=msg.classifier_result,
        metadata_json=dict(msg.metadata_json or {}),
        created_at=msg.created_at,
    )


def _load_history_for_conversation(db: Session, tenant_id: uuid.UUID, conv_id: uuid.UUID) -> list[dict[str, str]]:
    prior_rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv_id, Message.tenant_id == tenant_id)
        .order_by(Message.created_at.asc())
    ).all()
    history: list[dict[str, str]] = []
    for m in prior_rows:
        meta = dict(m.metadata_json or {})
        history.append(
            {
                "role": m.role,
                "content": m.content,
                "workflow_slug": str(meta.get("workflow_slug") or meta.get("agent_id") or ""),
            }
        )
    return history


def _enforce_rate_limit(
    principal: AuthenticatedPrincipal,
    *,
    bucket: str = "agent_execute",
    estimated_tokens: int = 0,
) -> None:
    allowed, retry_after, reason = rate_limiter.check_and_consume(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        bucket=bucket,
        estimated_tokens=estimated_tokens,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=reason,
            headers={"Retry-After": str(retry_after)},
        )


def _raise_if_policy_or_quota_blocked(state: dict[str, Any], db: Session) -> None:
    classifier_res = state.get("classifier_result")
    if classifier_res == "blocked_permission":
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=state.get("rejection_reason") or "Access denied for your current workspace role.",
        )
    if classifier_res == "blocked_quota":
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=state.get("rejection_reason") or "Monthly token quota exceeded for this workspace.",
        )


@router.get("/workspace")
def get_unified_hr_workspace(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Return the consolidated HireFlow AI Hiring & HR workspace state, metrics, quota, and 7 workflow statuses."""
    rentals_by_slug = ensure_tenant_hr_workflows(
        db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id
    )
    db.commit()

    specs = {s["agent_id"]: s for s in agent_registry.list_specs()}
    cfg_rows = db.scalars(
        select(AgentConfiguration).where(AgentConfiguration.tenant_id == principal.tenant_id)
    ).all()
    cfg_by_rental = {c.rental_id: c for c in cfg_rows}

    workflows_payload: list[dict[str, Any]] = []
    for slug in HR_WORKFLOW_SLUGS:
        rental = rentals_by_slug.get(slug)
        spec = specs.get(slug, {})
        cfg = cfg_by_rental.get(rental.id) if rental else None
        allowed_roles = WORKFLOW_ALLOWED_ROLES.get(slug, {"platform_admin", "business_owner", "business_admin"})
        workflows_payload.append(
            {
                "slug": slug,
                "name": HR_WORKFLOW_DISPLAY_NAMES.get(slug, slug),
                "description": ", ".join((spec.get("domain") or {}).get("allowed_topics", [])[:4]),
                "rental_id": str(rental.id) if rental else None,
                "status": rental.status if rental else "inactive",
                "allowed_for_current_role": principal.role in allowed_roles,
                "blind_screening_mode": bool(cfg.blind_screening_mode) if cfg else (slug == "recruitment-screening"),
                "strict_pii_masking": bool(cfg.strict_pii_masking) if cfg else True,
                "require_hitl_approval": bool(cfg.require_hitl_approval) if cfg else True,
                "model_routing_tier": cfg.model_routing_tier if cfg else "auto_cascade",
                "monthly_token_quota": int(cfg.monthly_token_quota) if cfg else 2_000_000,
                "extra_settings": dict(cfg.extra_settings or {}) if cfg else {},
            }
        )

    total_execs = int(
        db.scalar(select(func.count(ExecutionLog.id)).where(ExecutionLog.tenant_id == principal.tenant_id)) or 0
    )
    completed_execs = int(
        db.scalar(
            select(func.count(ExecutionLog.id)).where(
                ExecutionLog.tenant_id == principal.tenant_id,
                ExecutionLog.status.in_(["completed", "paused_hitl"]),
            )
        )
        or 0
    )
    rejected_execs = int(
        db.scalar(
            select(func.count(ExecutionLog.id)).where(
                ExecutionLog.tenant_id == principal.tenant_id,
                ExecutionLog.status == "rejected",
            )
        )
        or 0
    )
    failed_execs = int(
        db.scalar(
            select(func.count(ExecutionLog.id)).where(
                ExecutionLog.tenant_id == principal.tenant_id,
                ExecutionLog.status.in_(["failed", "error"]),
            )
        )
        or 0
    )
    blocked_execs = int(
        db.scalar(
            select(func.count(ExecutionLog.id)).where(
                ExecutionLog.tenant_id == principal.tenant_id,
                ExecutionLog.status == "blocked",
            )
        )
        or 0
    )
    pending_hitl = int(
        db.scalar(
            select(func.count(HitlApproval.id)).where(
                HitlApproval.tenant_id == principal.tenant_id,
                HitlApproval.status == "pending",
            )
        )
        or 0
    )
    candidate_count = int(
        db.scalar(select(func.count(Candidate.id)).where(Candidate.tenant_id == principal.tenant_id)) or 0
    )
    resume_docs_count = int(
        db.scalar(
            select(func.count(KnowledgeDocument.id)).where(
                KnowledgeDocument.tenant_id == principal.tenant_id,
                KnowledgeDocument.source_type == "resume",
            )
        )
        or 0
    )
    inline_resumes_count = int(
        db.scalar(
            select(func.count(Candidate.id)).where(
                Candidate.tenant_id == principal.tenant_id,
                Candidate.source_document_id.is_(None),
            )
        )
        or 0
    )
    resumes_analyzed_count = resume_docs_count + inline_resumes_count
    interview_count = int(
        db.scalar(select(func.count(InterviewRecord.id)).where(InterviewRecord.tenant_id == principal.tenant_id)) or 0
    )
    scheduled_interviews_count = int(
        db.scalar(
            select(func.count(InterviewRecord.id)).where(
                InterviewRecord.tenant_id == principal.tenant_id,
                InterviewRecord.status.in_(["scheduled", "proposed", "confirmed"]),
            )
        )
        or 0
    )
    onboarding_count = int(
        db.scalar(select(func.count(OnboardingWorkflow.id)).where(OnboardingWorkflow.tenant_id == principal.tenant_id)) or 0
    )
    pending_onboarding_count = int(
        db.scalar(
            select(func.count(OnboardingWorkflow.id)).where(
                OnboardingWorkflow.tenant_id == principal.tenant_id,
                OnboardingWorkflow.progress_percent < 100,
            )
        )
        or 0
    )
    kb_doc_count = int(
        db.scalar(select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.tenant_id == principal.tenant_id)) or 0
    )

    job_titles: set[str] = set()
    for role_val in db.scalars(
        select(Candidate.target_role).where(Candidate.tenant_id == principal.tenant_id)
    ).all():
        if role_val and str(role_val).strip():
            job_titles.add(str(role_val).strip().lower())
    for role_val in db.scalars(
        select(InterviewRecord.role_title).where(InterviewRecord.tenant_id == principal.tenant_id)
    ).all():
        if role_val and str(role_val).strip():
            job_titles.add(str(role_val).strip().lower())
    for doc_title in db.scalars(
        select(KnowledgeDocument.title).where(
            KnowledgeDocument.tenant_id == principal.tenant_id,
            KnowledgeDocument.source_type == "jd_template",
        )
    ).all():
        if doc_title and str(doc_title).strip():
            job_titles.add(str(doc_title).strip().lower())
    jd_rental = rentals_by_slug.get("jd-generator")
    if jd_rental is not None:
        for jd_preview in db.scalars(
            select(ExecutionLog.prompt_preview).where(
                ExecutionLog.tenant_id == principal.tenant_id,
                ExecutionLog.rental_id == jd_rental.id,
                ExecutionLog.status.in_(["completed", "paused_hitl"]),
            )
        ).all():
            if jd_preview and str(jd_preview).strip():
                job_titles.add(f"jd:{str(jd_preview).strip().lower()[:80]}")
    total_jobs_count = len(job_titles)

    from ...db.models import TokenUsage

    estimated_ai_cost_usd = round(
        float(
            db.scalar(
                select(func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0)).where(
                    TokenUsage.tenant_id == principal.tenant_id
                )
            )
            or 0.0
        ),
        6,
    )

    tokens_used_month = get_monthly_token_usage(db, tenant_id=principal.tenant_id)
    primary_cfg = cfg_by_rental.get(rentals_by_slug["hr-policy-support"].id) if "hr-policy-support" in rentals_by_slug else (cfg_rows[0] if cfg_rows else None)
    unified_cap = (
        int((primary_cfg.extra_settings or {}).get("unified_quota_limit"))
        if primary_cfg and (primary_cfg.extra_settings or {}).get("unified_quota_limit") is not None
        else (int(primary_cfg.monthly_token_quota) if primary_cfg else 2_000_000)
    )
    remaining_tokens = max(0, unified_cap - tokens_used_month)
    usage_percent = round(min(100.0, (tokens_used_month / max(1, unified_cap)) * 100.0), 1)

    return {
        "product_name": "HireFlow AI — Hiring & HR AI Agent",
        "tenant_id": str(principal.tenant_id),
        "organization_name": principal.organization_name,
        "organization_slug": principal.organization_slug,
        "role": principal.role,
        "workflows": workflows_payload,
        "metrics": {
            "total_executions": total_execs,
            "completed_executions": completed_execs,
            "failed_executions": failed_execs,
            "rejected_executions": rejected_execs,
            "blocked_executions": blocked_execs,
            "pending_hitl_count": pending_hitl,
            "total_jobs_count": total_jobs_count,
            "candidate_count": candidate_count,
            "resumes_analyzed_count": resumes_analyzed_count,
            "interview_count": interview_count,
            "scheduled_interviews_count": scheduled_interviews_count,
            "onboarding_count": onboarding_count,
            "pending_onboarding_count": pending_onboarding_count,
            "kb_document_count": kb_doc_count,
            "estimated_ai_cost_usd": estimated_ai_cost_usd,
        },
        "quota": {
            "monthly_token_limit": unified_cap,
            "tokens_used_this_month": tokens_used_month,
            "remaining_tokens": remaining_tokens,
            "usage_percent": usage_percent,
        },
        "settings": {
            "blind_screening_mode": bool(
                (cfg_by_rental.get(rentals_by_slug["recruitment-screening"].id).blind_screening_mode)
                if "recruitment-screening" in rentals_by_slug
                and rentals_by_slug["recruitment-screening"].id in cfg_by_rental
                else True
            ),
            "strict_pii_masking": bool(primary_cfg.strict_pii_masking) if primary_cfg else True,
            "require_hitl_approval": bool(primary_cfg.require_hitl_approval) if primary_cfg else True,
            "model_routing_tier": primary_cfg.model_routing_tier if primary_cfg else "auto_cascade",
            "monthly_token_quota": unified_cap,
            "custom_persona_prompt": primary_cfg.custom_persona_prompt if primary_cfg else "",
        },
    }


@router.post("/classify")
def classify_hr_request_preview(
    payload: UnifiedHrExecuteRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Dry-run intent & domain classifier inspection endpoint (runs zero tools and zero LLM generations unless ambiguous)."""
    target_slug = agent_registry.resolve_workflow_slug(
        user_input=payload.prompt,
        workflow_hint=payload.workflow_hint,
        structured_input=payload.structured_input,
        fallback_slug="hr-policy-support",
    )
    agent = agent_registry.get_agent(target_slug)
    intent = classify_intent_detailed(
        payload.prompt,
        target_slug,
        structured_input=payload.structured_input,
        allow_llm_fallback=True,
    )
    domain = classify_domain_boundary(
        payload.prompt,
        agent.agent_id,
        agent.domain,
        agent.guardrails,
        structured_input=payload.structured_input,
    )
    routed_wf = domain.suggested_agent_slug or intent.hr_workflow or target_slug
    return {
        "intent_analysis": intent.to_dict(),
        "domain_allowed": domain.allowed and not intent.is_injection and not intent.is_out_of_domain,
        "classifier_result": (
            "blocked_injection"
            if intent.is_injection
            else ("needs_clarification" if intent.needs_clarification else domain.classifier_result)
        ),
        "reason": domain.reason,
        "routed_workflow": routed_wf,
        "routed_workflow_name": HR_WORKFLOW_DISPLAY_NAMES.get(routed_wf, routed_wf),
    }


@router.post("/execute", response_model=UnifiedHrExecuteResponse)
def execute_unified_hr_agent(
    payload: UnifiedHrExecuteRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> UnifiedHrExecuteResponse:
    """
    Unified single-agent Hiring & HR entry point.
    Automatically classifies & routes internally across all 7 HR workflows, checks RBAC & concurrency-safe quota,
    executes the LangGraph workflow, and blocks non-HR or unauthorized requests cleanly.
    """
    _enforce_rate_limit(
        principal,
        bucket="agent_execute",
        estimated_tokens=max(1, (len(payload.prompt) + 3) // 4),
    )
    rentals_by_slug = ensure_tenant_hr_workflows(
        db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id
    )

    history: list[dict[str, str]] = []
    if payload.conversation_id is not None:
        conv = db.scalars(
            select(AgentConversation).where(
                AgentConversation.id == payload.conversation_id,
                AgentConversation.tenant_id == principal.tenant_id,
            )
        ).first()
        if conv is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        history = _load_history_for_conversation(db, principal.tenant_id, conv.id)

    target_slug = agent_registry.resolve_workflow_slug(
        user_input=payload.prompt,
        workflow_hint=payload.workflow_hint,
        conversation_history=history,
        structured_input=payload.structured_input,
        fallback_slug="hr-policy-support",
    )
    target_rental = rentals_by_slug.get(target_slug)
    if target_rental is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="HR workflow not provisioned")

    state = agent_registry.execute(
        agent_slug=target_slug,
        db=db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        user_input=payload.prompt.strip(),
        rental_id=target_rental.id,
        conversation_id=payload.conversation_id,
        structured_input=payload.structured_input,
        attachments=payload.attachments,
        conversation_history=history,
        model_provider_override=payload.model_provider_override,
        persist_telemetry=True,
        enable_optimization=payload.enable_optimization,
    )
    _raise_if_policy_or_quota_blocked(state, db)
    rate_limiter.record_tokens(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        bucket="agent_execute",
        tokens=int(state.get("input_tokens", 0)) + int(state.get("output_tokens", 0)),
    )
    db.commit()

    routed_wf = str(state.get("selected_agent_id") or state.get("routed_agent_id") or target_slug)
    base_in = int(state.get("baseline_input_tokens") or state.get("input_tokens", 0))
    actual_in = int(state.get("input_tokens", 0))
    opt_enabled = bool(state.get("enable_optimization", True))
    tokens_saved = max(0, base_in - actual_in) if opt_enabled else 0
    reduction_pct = round((tokens_saved / base_in) * 100.0, 2) if (opt_enabled and base_in > 0) else 0.0
    return UnifiedHrExecuteResponse(
        execution_status=state.get("execution_status", "completed"),
        classifier_result=state.get("classifier_result", "in_domain"),
        routed_workflow=routed_wf,
        routed_workflow_name=HR_WORKFLOW_DISPLAY_NAMES.get(routed_wf, routed_wf),
        requested_workflow=str(state.get("requested_agent_id") or target_slug),
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
        baseline_input_tokens=base_in,
        input_tokens=actual_in,
        cached_tokens=int(state.get("cached_tokens", 0)),
        output_tokens=int(state.get("output_tokens", 0)),
        tokens_saved=tokens_saved,
        reduction_percent=reduction_pct,
        optimization_enabled=opt_enabled,
        optimization_methods_used=list(state.get("optimization_methods_used") or []),
        guardrail_flags=list(state.get("guardrail_flags") or []),
        intent_analysis=dict(state.get("intent_analysis") or {}),
        clarification_questions=list(state.get("clarification_questions") or []),
        latency_ms=int(state.get("latency_ms", 0)),
        rejection_reason=state.get("rejection_reason"),
    )


@router.get("/conversations", response_model=list[ConversationResponse])
def list_unified_conversations(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[ConversationResponse]:
    ensure_tenant_hr_workflows(db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id)
    convs = db.scalars(
        select(AgentConversation)
        .where(AgentConversation.tenant_id == principal.tenant_id)
        .order_by(AgentConversation.updated_at.desc())
        .limit(50)
    ).all()
    out: list[ConversationResponse] = []
    for conv in convs:
        msg_count = int(
            db.scalar(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conv.id,
                    Message.tenant_id == principal.tenant_id,
                )
            )
            or 0
        )
        out.append(
            ConversationResponse(
                id=conv.id,
                tenant_id=conv.tenant_id,
                rental_id=conv.rental_id,
                user_id=conv.user_id,
                title=conv.title,
                status=conv.status,
                message_count=msg_count,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
            )
        )
    db.commit()
    return out


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_unified_conversation(
    payload: UnifiedConversationCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> ConversationResponse:
    rentals_by_slug = ensure_tenant_hr_workflows(
        db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id
    )
    primary_rental = rentals_by_slug.get("hr-policy-support") or next(iter(rentals_by_slug.values()))
    conv = AgentConversation(
        tenant_id=principal.tenant_id,
        rental_id=primary_rental.id,
        user_id=principal.user_id,
        title=payload.title.strip(),
        status="active",
        summary_memory="",
    )
    db.add(conv)
    db.flush()
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=primary_rental.id,
        action="hr_agent.conversation_created",
        resource_type="agent_conversation",
        resource_id=str(conv.id),
        ip_address=principal.ip_address,
        metadata={"title": conv.title},
    )
    resp = ConversationResponse(
        id=conv.id,
        tenant_id=conv.tenant_id,
        rental_id=conv.rental_id,
        user_id=conv.user_id,
        title=conv.title,
        status=conv.status,
        message_count=0,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )
    db.commit()
    return resp


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
def list_unified_conversation_messages(
    conversation_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[MessageResponse]:
    conv = db.scalars(
        select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.tenant_id == principal.tenant_id,
        )
    ).first()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conv.id, Message.tenant_id == principal.tenant_id)
        .order_by(Message.created_at.asc())
    ).all()
    return [_to_msg_resp(m) for m in rows]


@router.post("/conversations/{conversation_id}/messages", response_model=UnifiedMessageTurnResponse, status_code=status.HTTP_201_CREATED)
def post_unified_conversation_message(
    conversation_id: uuid.UUID,
    payload: UnifiedMessageCreateRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> UnifiedMessageTurnResponse:
    _enforce_rate_limit(
        principal,
        bucket="agent_execute",
        estimated_tokens=max(1, (len(payload.content) + 3) // 4),
    )
    conv = db.scalars(
        select(AgentConversation).where(
            AgentConversation.id == conversation_id,
            AgentConversation.tenant_id == principal.tenant_id,
        )
    ).first()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    rentals_by_slug = ensure_tenant_hr_workflows(
        db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id
    )
    history = _load_history_for_conversation(db, principal.tenant_id, conv.id)

    prior_wf = next((m.get("workflow_slug") for m in reversed(history) if m.get("workflow_slug")), "") or "hr-policy-support"
    target_slug = agent_registry.resolve_workflow_slug(
        user_input=payload.content.strip(),
        workflow_hint=payload.workflow_hint,
        conversation_history=history,
        structured_input=payload.structured_input,
        fallback_slug=prior_wf,
    )
    target_rental = rentals_by_slug.get(target_slug) or next(iter(rentals_by_slug.values()))

    state = agent_registry.execute(
        agent_slug=target_slug,
        db=db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        user_input=payload.content.strip(),
        rental_id=target_rental.id,
        conversation_id=conv.id,
        structured_input=payload.structured_input,
        attachments=payload.attachments,
        conversation_history=history,
        model_provider_override=payload.model_provider_override,
        persist_telemetry=True,
        enable_optimization=payload.enable_optimization,
    )
    _raise_if_policy_or_quota_blocked(state, db)
    rate_limiter.record_tokens(
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        bucket="agent_execute",
        tokens=int(state.get("input_tokens", 0)) + int(state.get("output_tokens", 0)),
    )

    classifier_res = state.get("classifier_result", "in_domain")
    exec_status = state.get("execution_status", "completed")
    selected_wf = str(state.get("selected_agent_id") or state.get("routed_agent_id") or target_slug)
    wf_name = HR_WORKFLOW_DISPLAY_NAMES.get(selected_wf, selected_wf)
    assistant_role = "assistant" if classifier_res == "in_domain" else "system_guardrail"

    user_msg = Message(
        tenant_id=principal.tenant_id,
        conversation_id=conv.id,
        role="user",
        content=payload.content.strip(),
        classifier_result=classifier_res,
        metadata_json={"actor_role": principal.role, "workflow_slug": selected_wf},
    )
    db.add(user_msg)
    db.flush()

    assistant_msg = Message(
        tenant_id=principal.tenant_id,
        conversation_id=conv.id,
        role=assistant_role,
        content=state.get("final_response_text", ""),
        classifier_result=classifier_res,
        metadata_json={
            "agent_id": selected_wf,
            "workflow_slug": selected_wf,
            "workflow_name": wf_name,
            "agent_version": state.get("selected_agent_version", "1.0.0"),
            "provider_used": state.get("llm_provider_used", "deterministic"),
            "model_used": state.get("model_used", "deterministic"),
            "citations": state.get("citations", []),
            "charts": state.get("charts", []),
            "hitl_requests": state.get("hitl_requests", []),
            "execution_status": exec_status,
            "execution_log_id": state.get("execution_log_id"),
            "trace_steps": state.get("trace_steps", []),
            "baseline_input_tokens": int(state.get("baseline_input_tokens") or state.get("input_tokens", 0)),
            "optimization_methods_used": list(state.get("optimization_methods_used") or []),
            "guardrail_flags": list(state.get("guardrail_flags") or []),
            "intent_analysis": dict(state.get("intent_analysis") or {}),
            "clarification_questions": list(state.get("clarification_questions") or []),
        },
    )
    db.add(assistant_msg)
    conv.updated_at = datetime.now(timezone.utc)
    if state.get("conversation_summary"):
        conv.summary_memory = str(state.get("conversation_summary", ""))[:2000]
    db.flush()

    resp = UnifiedMessageTurnResponse(
        conversation_id=conv.id,
        user_message=_to_msg_resp(user_msg),
        assistant_message=_to_msg_resp(assistant_msg),
        workflow_slug=selected_wf,
        workflow_name=wf_name,
        execution_status=exec_status,
        classifier_result=classifier_res,
        citations=list(state.get("citations") or []),
        charts=list(state.get("charts") or []),
        hitl_requests=list(state.get("hitl_requests") or []),
        trace_steps=[dict(s) for s in (state.get("trace_steps") or [])],
        baseline_input_tokens=int(state.get("baseline_input_tokens") or state.get("input_tokens", 0)),
        input_tokens=int(state.get("input_tokens", 0)),
        cached_tokens=int(state.get("cached_tokens", 0)),
        output_tokens=int(state.get("output_tokens", 0)),
        optimization_methods_used=list(state.get("optimization_methods_used") or []),
        guardrail_flags=list(state.get("guardrail_flags") or []),
        intent_analysis=dict(state.get("intent_analysis") or {}),
        clarification_questions=list(state.get("clarification_questions") or []),
        latency_ms=int(state.get("latency_ms", 0)),
    )
    db.commit()
    return resp


@router.get("/knowledge")
def list_unified_knowledge_documents(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    docs = db.scalars(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.tenant_id == principal.tenant_id)
        .order_by(KnowledgeDocument.created_at.desc())
    ).all()
    rentals_by_id = {
        r.id: cat.slug
        for r, cat in db.execute(
            select(AgentRental, AgentCatalog)
            .join(AgentCatalog, AgentCatalog.id == AgentRental.agent_id)
            .where(AgentRental.tenant_id == principal.tenant_id)
        ).all()
    }
    caller_lvl = ROLE_LEVEL.get(principal.role, 1)
    visible = [d for d in docs if ROLE_LEVEL.get(d.min_role_access, 1) <= caller_lvl]
    return [
        {
            "id": str(d.id),
            "rental_id": str(d.rental_id),
            "workflow_slug": rentals_by_id.get(d.rental_id, "hr-policy-support"),
            "workflow_name": HR_WORKFLOW_DISPLAY_NAMES.get(rentals_by_id.get(d.rental_id, "hr-policy-support"), "HR Knowledge"),
            "title": d.title,
            "original_filename": d.original_filename,
            "source_type": d.source_type,
            "mime_type": d.mime_type,
            "file_size_bytes": d.file_size_bytes,
            "sha256_checksum": d.sha256_checksum,
            "chunk_count": d.chunk_count,
            "min_role_access": d.min_role_access,
            "status": d.status,
            "created_at": d.created_at.isoformat(),
        }
        for d in visible
    ]


@router.post("/knowledge", status_code=status.HTTP_201_CREATED)
async def upload_unified_knowledge_document(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=200),
    source_type: str = Form(default="handbook"),
    min_role_access: str = Form(default="business_employee"),
    workflow_slug: str = Form(default="hr-policy-support"),
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    if min_role_access not in ROLE_LEVEL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid min_role_access value")

    rentals_by_slug = ensure_tenant_hr_workflows(
        db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id
    )
    canonical_slug = agent_registry.normalize_slug(workflow_slug)
    rental = rentals_by_slug.get(canonical_slug) or rentals_by_slug.get("hr-policy-support")
    if rental is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Workspace not initialized")

    doc_id = uuid.uuid4()
    rel_path, sha_hex, byte_len, safe_name = await save_tenant_upload(
        tenant_id=principal.tenant_id,
        rental_id=rental.id,
        doc_id=doc_id,
        upload=file,
    )
    content_type = (file.content_type or "application/octet-stream")[:120]

    doc = KnowledgeDocument(
        id=doc_id,
        tenant_id=principal.tenant_id,
        rental_id=rental.id,
        uploaded_by_user_id=principal.user_id,
        title=title.strip(),
        original_filename=safe_name,
        source_type=source_type.strip().lower(),
        mime_type=content_type,
        file_size_bytes=byte_len,
        storage_rel_path=rel_path,
        sha256_checksum=sha_hex,
        chunk_count=1,
        min_role_access=min_role_access,
        status="indexing",
    )
    db.add(doc)
    db.flush()

    saved_path = resolve_tenant_file(principal.tenant_id, rel_path)
    raw_blob = saved_path.read_bytes()
    extracted = extract_document_text(raw_blob, filename=safe_name, mime_type=content_type)
    if len(re.findall(r"[A-Za-z0-9]", extracted or "")) < 8:
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        db.delete(doc)
        record_audit(
            db,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            rental_id=rental.id,
            action="security.invalid_document_rejected",
            resource_type="knowledge_document",
            resource_id=str(doc.id),
            ip_address=principal.ip_address,
            status="blocked",
            metadata={"filename": safe_name, "reason": "empty_or_unreadable_document"},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document or resume is empty, corrupted, or contains no readable text.",
        )
    sec_check = inspect_document_bytes(
        raw_blob,
        filename=safe_name,
        mime_type=content_type,
        extracted_text=extracted,
        allow_indirect_text_neutralization=False,
    )
    if not sec_check.is_safe_for_upload:
        if saved_path.exists():
            saved_path.unlink(missing_ok=True)
        db.delete(doc)
        record_audit(
            db,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            rental_id=rental.id,
            action="security.malicious_document_blocked",
            resource_type="knowledge_document",
            resource_id=str(doc.id),
            ip_address=principal.ip_address,
            status="blocked",
            metadata={"filename": safe_name, "threats": sec_check.threats_detected},
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=sec_check.blocked_reason)

    chunk_count = index_document_chunks(db, doc=doc, text_content=extracted)
    doc.chunk_count = max(1, chunk_count)
    doc.status = "indexed"

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=rental.id,
        action="knowledge.document_uploaded",
        resource_type="knowledge_document",
        resource_id=str(doc.id),
        ip_address=principal.ip_address,
        metadata={"filename": safe_name, "bytes": byte_len, "min_role_access": min_role_access, "chunks": doc.chunk_count},
    )
    db.commit()

    return {
        "id": str(doc.id),
        "rental_id": str(doc.rental_id),
        "workflow_slug": canonical_slug if canonical_slug in HR_WORKFLOW_DISPLAY_NAMES else "hr-policy-support",
        "workflow_name": HR_WORKFLOW_DISPLAY_NAMES.get(canonical_slug, "HR Knowledge"),
        "title": doc.title,
        "original_filename": doc.original_filename,
        "source_type": doc.source_type,
        "mime_type": doc.mime_type,
        "file_size_bytes": doc.file_size_bytes,
        "sha256_checksum": doc.sha256_checksum,
        "chunk_count": doc.chunk_count,
        "min_role_access": doc.min_role_access,
        "status": doc.status,
        "created_at": doc.created_at.isoformat(),
    }


@router.get("/knowledge/{doc_id}/download")
def download_unified_knowledge_document(
    doc_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> FileResponse:
    doc = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.tenant_id == principal.tenant_id,
        )
    ).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    if ROLE_LEVEL.get(principal.role, 1) < ROLE_LEVEL.get(doc.min_role_access, 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role privilege to access this document",
        )

    target = resolve_tenant_file(principal.tenant_id, doc.storage_rel_path)
    if not target.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file blob not found on storage")

    return FileResponse(path=str(target), filename=doc.original_filename, media_type=doc.mime_type)


@router.delete("/knowledge/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unified_knowledge_document(
    doc_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> None:
    doc = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.tenant_id == principal.tenant_id,
        )
    ).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    try:
        blob = resolve_tenant_file(principal.tenant_id, doc.storage_rel_path)
        if blob.exists():
            blob.unlink()
    except HTTPException:
        pass

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=doc.rental_id,
        action="knowledge.document_deleted",
        resource_type="knowledge_document",
        resource_id=str(doc.id),
        ip_address=principal.ip_address,
        metadata={"filename": doc.original_filename},
    )
    db.delete(doc)
    db.commit()
    tenant_response_cache.invalidate_tenant(principal.tenant_id)


@router.get("/knowledge/{doc_id}/markdown")
def export_knowledge_document_obsidian_markdown(
    doc_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Export an indexed tenant HR document as Obsidian-compatible Markdown (YAML frontmatter + [[wikilinks]])."""
    doc = db.scalars(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.tenant_id == principal.tenant_id,
        )
    ).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    if ROLE_LEVEL.get(principal.role, 1) < ROLE_LEVEL.get(doc.min_role_access, 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient role privilege to access this document",
        )

    chunks = db.scalars(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == doc.id, KnowledgeChunk.tenant_id == principal.tenant_id)
        .order_by(KnowledgeChunk.chunk_index.asc())
    ).all()
    markdown = export_document_as_obsidian_markdown(doc, list(chunks))
    meta = dict((chunks[0].metadata_json or {}) if chunks else {})
    return {
        "document_id": str(doc.id),
        "title": doc.title,
        "filename": f"{doc.original_filename.rsplit('.', 1)[0]}.md",
        "markdown": markdown,
        "tags": list(meta.get("tags") or []),
        "wikilinks": list(meta.get("wikilinks") or []),
    }


@router.get("/knowledge-graph")
def get_tenant_hr_knowledge_graph(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    """Return tenant-isolated relational HR knowledge graph (documents, tags, [[wikilinks]], skills, candidates)."""
    include_pii = principal.role in {"platform_admin", "business_owner", "business_admin"}
    return build_tenant_hr_graph(db, principal.tenant_id, include_pii=include_pii)


@router.get("/integrations")
def list_unified_integrations(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    ensure_tenant_hr_workflows(db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id)
    rows = db.execute(
        select(ToolPermission, ToolRegistry, AgentRental, AgentCatalog)
        .join(ToolRegistry, ToolPermission.tool_id == ToolRegistry.id)
        .join(AgentRental, ToolPermission.rental_id == AgentRental.id)
        .join(AgentCatalog, AgentRental.agent_id == AgentCatalog.id)
        .where(ToolPermission.tenant_id == principal.tenant_id)
        .order_by(AgentCatalog.name.asc(), ToolRegistry.name.asc())
    ).all()
    db.commit()

    return [
        {
            "id": str(perm.id),
            "rental_id": str(perm.rental_id),
            "workflow_slug": cat.slug,
            "workflow_name": HR_WORKFLOW_DISPLAY_NAMES.get(cat.slug, cat.name),
            "tool_id": str(tool.id),
            "tool_slug": tool.slug,
            "tool_name": tool.name,
            "category": tool.category,
            "mcp_server_slug": tool.mcp_server_slug,
            "execution_mode": tool.execution_mode,
            "requires_hitl": tool.requires_hitl,
            "auth_scheme": tool.auth_scheme,
            "description": tool.description,
            "is_allowed": perm.is_allowed,
            "credential_status": perm.credential_status,
            "masked_secret_ref": perm.masked_secret_ref,
        }
        for perm, tool, _rental, cat in rows
    ]


@router.patch("/integrations/{permission_id}")
def update_unified_integration_permission(
    permission_id: uuid.UUID,
    payload: UnifiedToolUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    perm = db.scalars(
        select(ToolPermission).where(
            ToolPermission.id == permission_id,
            ToolPermission.tenant_id == principal.tenant_id,
        )
    ).first()
    if perm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration permission not found")
    tool = db.get(ToolRegistry, perm.tool_id)

    if payload.apply_to_all_workflows:
        matching = db.scalars(
            select(ToolPermission).where(
                ToolPermission.tenant_id == principal.tenant_id,
                ToolPermission.tool_id == perm.tool_id,
            )
        ).all()
        for p in matching:
            p.is_allowed = payload.is_allowed
    else:
        perm.is_allowed = payload.is_allowed

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=perm.rental_id,
        action="hr_integration.permission_updated",
        resource_type="tool_permission",
        resource_id=str(perm.id),
        ip_address=principal.ip_address,
        metadata={"tool_slug": tool.slug if tool else "", "is_allowed": payload.is_allowed},
    )
    db.commit()
    return {
        "id": str(perm.id),
        "tool_slug": tool.slug if tool else "",
        "is_allowed": perm.is_allowed,
        "credential_status": perm.credential_status,
        "masked_secret_ref": perm.masked_secret_ref,
    }


@router.post("/integrations/{permission_id}/credentials")
def bind_unified_integration_credential(
    permission_id: uuid.UUID,
    payload: UnifiedToolCredentialRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    perm = db.scalars(
        select(ToolPermission).where(
            ToolPermission.id == permission_id,
            ToolPermission.tenant_id == principal.tenant_id,
        )
    ).first()
    if perm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration permission not found")
    tool = db.get(ToolRegistry, perm.tool_id)
    if tool is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool registry entry not found")

    secret_plain = payload.api_key_or_token.strip()
    encrypted = encrypt_secret(secret_plain)
    masked = mask_secret(secret_plain, principal.tenant_id, tool.slug)

    targets = (
        db.scalars(
            select(ToolPermission).where(
                ToolPermission.tenant_id == principal.tenant_id,
                ToolPermission.tool_id == perm.tool_id,
            )
        ).all()
        if payload.apply_to_all_workflows
        else [perm]
    )
    for item in targets:
        item.encrypted_secret = encrypted
        item.credential_status = "bound_encrypted"
        item.masked_secret_ref = masked

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        rental_id=perm.rental_id,
        action="hr_integration.credential_bound",
        resource_type="tool_permission",
        resource_id=str(perm.id),
        ip_address=principal.ip_address,
        metadata={"tool_slug": tool.slug, "masked_ref": masked},
    )
    db.commit()
    return {
        "id": str(perm.id),
        "tool_slug": tool.slug,
        "is_allowed": perm.is_allowed,
        "credential_status": perm.credential_status,
        "masked_secret_ref": perm.masked_secret_ref,
    }


@router.patch("/settings")
def update_unified_hr_settings(
    payload: UnifiedSettingsUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    ensure_tenant_hr_workflows(db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id)
    cfg_rows = db.scalars(
        select(AgentConfiguration)
        .where(AgentConfiguration.tenant_id == principal.tenant_id)
        .order_by(AgentConfiguration.id)
        .with_for_update()
    ).all()

    for cfg in cfg_rows:
        if payload.blind_screening_mode is not None:
            cfg.blind_screening_mode = payload.blind_screening_mode
        if payload.strict_pii_masking is not None:
            cfg.strict_pii_masking = payload.strict_pii_masking
        if payload.require_hitl_approval is not None:
            cfg.require_hitl_approval = payload.require_hitl_approval
        if payload.model_routing_tier is not None:
            cfg.model_routing_tier = payload.model_routing_tier
        if payload.monthly_token_quota is not None:
            cfg.monthly_token_quota = payload.monthly_token_quota
            extra = dict(cfg.extra_settings or {})
            extra["unified_quota_limit"] = int(payload.monthly_token_quota)
            cfg.extra_settings = extra
        if payload.custom_persona_prompt is not None:
            cfg.custom_persona_prompt = payload.custom_persona_prompt.strip()
        cfg.config_hash = _compute_config_hash(
            cfg.rental_id,
            cfg.custom_persona_prompt,
            cfg.model_routing_tier,
            cfg.blind_screening_mode,
        )

    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="hr_agent.settings_updated",
        resource_type="tenant_workspace",
        resource_id=str(principal.tenant_id),
        ip_address=principal.ip_address,
        metadata={
            "monthly_token_quota": payload.monthly_token_quota,
            "model_routing_tier": payload.model_routing_tier,
            "blind_screening_mode": payload.blind_screening_mode,
        },
    )
    db.commit()
    tenant_response_cache.invalidate_tenant(principal.tenant_id)

    sample = cfg_rows[0] if cfg_rows else None
    used_month = get_monthly_token_usage(db, tenant_id=principal.tenant_id)
    cap = (
        int((sample.extra_settings or {}).get("unified_quota_limit"))
        if sample and (sample.extra_settings or {}).get("unified_quota_limit") is not None
        else (int(sample.monthly_token_quota) if sample else 2_000_000)
    )
    return {
        "blind_screening_mode": bool(sample.blind_screening_mode) if sample else True,
        "strict_pii_masking": bool(sample.strict_pii_masking) if sample else True,
        "require_hitl_approval": bool(sample.require_hitl_approval) if sample else True,
        "model_routing_tier": sample.model_routing_tier if sample else "auto_cascade",
        "monthly_token_quota": cap,
        "tokens_used_this_month": used_month,
        "custom_persona_prompt": sample.custom_persona_prompt if sample else "",
    }


@router.get("/executions")
def list_unified_executions(
    workflow_slug: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[dict[str, Any]]:
    stmt = (
        select(ExecutionLog)
        .where(ExecutionLog.tenant_id == principal.tenant_id)
        .order_by(ExecutionLog.created_at.desc())
        .limit(limit)
    )
    if status_filter:
        stmt = stmt.where(ExecutionLog.status == status_filter)
    rows = db.scalars(stmt).all()
    out: list[dict[str, Any]] = []
    for log in rows:
        meta = dict(log.browser_activity_json or {})
        telemetry = dict(log.runtime_telemetry_json or {})
        wf = str(meta.get("agent_slug") or "hr-workflow")
        if workflow_slug and wf != workflow_slug:
            continue
        if meta.get("status") == "idle":
            meta["status"] = "not_used"
        out.append(
            {
                "id": str(log.id),
                "rental_id": str(log.rental_id),
                "workflow_slug": wf,
                "workflow_name": HR_WORKFLOW_DISPLAY_NAMES.get(wf, wf),
                "prompt_preview": log.prompt_preview,
                "classifier_result": log.classifier_result,
                "status": log.status,
                "latency_ms": log.latency_ms,
                "model_tier_used": log.model_tier_used,
                "steps_json": list(log.steps_json or []),
                "citations_json": list(log.citations_json or []),
                "tools": list(meta.get("tools") or []),
                "tool_calls": telemetry.get("tool_calls", []),
                "browser_activity": meta,
                "sandbox_status": telemetry.get(
                    "sandbox",
                    {"status": "not_used", "backend_mode": "none", "is_container_isolated": False},
                ),
                "intent_analysis": telemetry.get("intent_analysis", {}),
                "guardrail_flags": telemetry.get("guardrail_flags", []),
                "optimization": telemetry.get("optimization", {}),
                "token_usage": telemetry.get(
                    "token_usage",
                    {
                        "baseline_input_tokens": 0,
                        "input_tokens": 0,
                        "cached_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "estimated_cost_usd": 0.0,
                    },
                ),
                "created_at": log.created_at.isoformat(),
            }
        )
    return out


@router.get("/usage")
def get_unified_usage_breakdown(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    ensure_tenant_hr_workflows(db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id)
    tokens = db.scalars(
        select(TokenUsage)
        .where(TokenUsage.tenant_id == principal.tenant_id)
        .order_by(TokenUsage.created_at.desc())
        .limit(200)
    ).all()
    cfg = db.scalars(select(AgentConfiguration).where(AgentConfiguration.tenant_id == principal.tenant_id)).first()
    monthly_used = get_monthly_token_usage(db, tenant_id=principal.tenant_id)
    monthly_limit = (
        int((cfg.extra_settings or {}).get("unified_quota_limit"))
        if cfg and (cfg.extra_settings or {}).get("unified_quota_limit") is not None
        else (int(cfg.monthly_token_quota) if cfg else 2_000_000)
    )

    by_workflow: dict[str, dict[str, Any]] = {}
    methods_frequency: dict[str, int] = {}
    total_baseline_in = 0
    total_actual_in = 0
    total_cached = 0
    total_output = 0
    total_cost = 0.0
    total_saved = 0
    opt_runs: list[TokenUsage] = []
    unopt_runs: list[TokenUsage] = []

    for t in tokens:
        wf = t.step_name
        base_in = int(t.baseline_input_tokens or t.input_tokens)
        act_in = int(t.input_tokens)
        cached = int(t.cached_tokens)
        out_t = int(t.output_tokens)
        cost_val = float(t.estimated_cost_usd or Decimal("0"))
        saved_row = max(0, base_in - act_in) if bool(t.optimization_enabled) else 0

        total_baseline_in += base_in
        total_actual_in += act_in
        total_cached += cached
        total_output += out_t
        total_cost += cost_val
        total_saved += saved_row

        if bool(t.optimization_enabled):
            opt_runs.append(t)
        else:
            unopt_runs.append(t)

        for method in list(t.optimization_methods_json or []):
            methods_frequency[str(method)] = methods_frequency.get(str(method), 0) + 1

        bucket = by_workflow.setdefault(
            wf,
            {
                "workflow_slug": wf,
                "workflow_name": HR_WORKFLOW_DISPLAY_NAMES.get(wf, wf),
                "baseline_input_tokens": 0,
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "tokens_saved": 0,
                "tool_calls_count": 0,
                "total_duration_ms": 0,
                "avg_duration_ms": 0.0,
                "estimated_cost_usd": 0.0,
                "runs": 0,
            },
        )
        bucket["baseline_input_tokens"] += base_in
        bucket["input_tokens"] += act_in
        bucket["cached_tokens"] += cached
        bucket["output_tokens"] += out_t
        bucket["total_tokens"] += act_in + out_t
        bucket["tokens_saved"] += saved_row
        bucket["tool_calls_count"] += int(t.tool_calls_count or 0)
        bucket["total_duration_ms"] += int(t.duration_ms or 0)
        bucket["estimated_cost_usd"] += cost_val
        bucket["runs"] += 1

    for bucket in by_workflow.values():
        runs_cnt = max(1, bucket["runs"])
        bucket["avg_duration_ms"] = round(bucket["total_duration_ms"] / runs_cnt, 1)

    measured_reduction_pct = (
        round((total_saved / total_baseline_in) * 100.0, 2) if total_baseline_in > 0 else 0.0
    )
    avg_opt_in = (
        round(sum(int(r.input_tokens) for r in opt_runs) / len(opt_runs), 1) if opt_runs else None
    )
    avg_unopt_in = (
        round(sum(int(r.input_tokens) for r in unopt_runs) / len(unopt_runs), 1) if unopt_runs else None
    )

    db.commit()
    return {
        "monthly_token_limit": monthly_limit,
        "tokens_used_this_month": monthly_used,
        "remaining_tokens": max(0, monthly_limit - monthly_used),
        "optimization_summary": {
            "total_runs_measured": len(tokens),
            "optimized_runs": len(opt_runs),
            "unoptimized_runs": len(unopt_runs),
            "total_baseline_input_tokens": total_baseline_in,
            "total_actual_input_tokens": total_actual_in,
            "total_cached_tokens": total_cached,
            "total_output_tokens": total_output,
            "total_measured_tokens_saved": total_saved,
            "measured_reduction_percent": measured_reduction_pct,
            "total_estimated_cost_usd": round(total_cost, 6),
            "avg_optimized_input_tokens": avg_opt_in,
            "avg_unoptimized_input_tokens": avg_unopt_in,
            "methods_frequency": methods_frequency,
        },
        "by_workflow": list(by_workflow.values()),
        "recent_entries": [
            {
                "id": str(t.id),
                "workflow_slug": t.step_name,
                "workflow_name": HR_WORKFLOW_DISPLAY_NAMES.get(t.step_name, t.step_name),
                "model_id": t.model_id,
                "baseline_input_tokens": int(t.baseline_input_tokens or t.input_tokens),
                "input_tokens": int(t.input_tokens),
                "cached_tokens": int(t.cached_tokens),
                "output_tokens": int(t.output_tokens),
                "duration_ms": int(t.duration_ms or 0),
                "tool_calls_count": int(t.tool_calls_count or 0),
                "optimization_enabled": bool(t.optimization_enabled),
                "optimization_methods": list(t.optimization_methods_json or []),
                "estimated_cost_usd": str(t.estimated_cost_usd),
                "created_at": t.created_at.isoformat(),
            }
            for t in tokens[:50]
        ],
    }


@router.post("/optimization/compare")
def compare_unoptimized_vs_optimized_execution(
    payload: OptimizationCompareRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    """
    Execute the same HR request both unoptimized and optimized against real tenant context & tools
    and report exact measured input/output token counts, latency, cost, and cache behavior.
    """
    _enforce_rate_limit(
        principal,
        bucket="optimization_compare",
        estimated_tokens=max(1, ((len(payload.prompt) + 3) // 4) * 2),
    )
    rentals_by_slug = ensure_tenant_hr_workflows(
        db, tenant_id=principal.tenant_id, actor_user_id=principal.user_id
    )
    target_slug = agent_registry.resolve_workflow_slug(
        user_input=payload.prompt,
        workflow_hint=payload.workflow_hint,
        structured_input=payload.structured_input,
        fallback_slug="hr-policy-support",
    )
    target_rental = rentals_by_slug.get(target_slug)
    if target_rental is None:
        raise HTTPException(status_code=500, detail="HR workflow not provisioned")

    # Ensure uncached fresh pass for honest cold vs optimized comparison
    tenant_response_cache.invalidate_tenant(principal.tenant_id)

    unopt_state = agent_registry.execute(
        agent_slug=target_slug,
        db=db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        user_input=payload.prompt.strip(),
        rental_id=target_rental.id,
        structured_input=payload.structured_input,
        persist_telemetry=payload.record_telemetry,
        enable_optimization=False,
    )
    _raise_if_policy_or_quota_blocked(unopt_state, db)

    opt_state = agent_registry.execute(
        agent_slug=target_slug,
        db=db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
        user_input=payload.prompt.strip(),
        rental_id=target_rental.id,
        structured_input=payload.structured_input,
        persist_telemetry=payload.record_telemetry,
        enable_optimization=True,
    )
    _raise_if_policy_or_quota_blocked(opt_state, db)
    db.commit()

    unopt_in = int(unopt_state.get("input_tokens", 0))
    unopt_out = int(unopt_state.get("output_tokens", 0))
    opt_in = int(opt_state.get("input_tokens", 0))
    opt_out = int(opt_state.get("output_tokens", 0))
    saved_in = max(0, unopt_in - opt_in)
    saved_total = max(0, (unopt_in + unopt_out) - (opt_in + opt_out))
    reduction_pct = round((saved_in / unopt_in) * 100.0, 2) if unopt_in > 0 else 0.0
    cost_saved = round(
        max(0.0, float(unopt_state.get("estimated_cost_usd", 0.0)) - float(opt_state.get("estimated_cost_usd", 0.0))),
        6,
    )

    return {
        "workflow_slug": str(opt_state.get("selected_agent_id") or target_slug),
        "workflow_name": HR_WORKFLOW_DISPLAY_NAMES.get(
            str(opt_state.get("selected_agent_id") or target_slug), target_slug
        ),
        "unoptimized": {
            "execution_status": unopt_state.get("execution_status"),
            "model_used": unopt_state.get("model_used"),
            "input_tokens": unopt_in,
            "cached_tokens": int(unopt_state.get("cached_tokens", 0)),
            "output_tokens": unopt_out,
            "total_tokens": unopt_in + unopt_out,
            "estimated_cost_usd": float(unopt_state.get("estimated_cost_usd", 0.0)),
            "latency_ms": int(unopt_state.get("latency_ms", 0)),
        },
        "optimized": {
            "execution_status": opt_state.get("execution_status"),
            "model_used": opt_state.get("model_used"),
            "baseline_input_tokens": int(opt_state.get("baseline_input_tokens") or unopt_in),
            "input_tokens": opt_in,
            "cached_tokens": int(opt_state.get("cached_tokens", 0)),
            "output_tokens": opt_out,
            "total_tokens": opt_in + opt_out,
            "estimated_cost_usd": float(opt_state.get("estimated_cost_usd", 0.0)),
            "latency_ms": int(opt_state.get("latency_ms", 0)),
            "methods_used": list(opt_state.get("optimization_methods_used") or []),
        },
        "measured_diff": {
            "input_tokens_saved": saved_in,
            "total_tokens_saved": saved_total,
            "input_reduction_percent": reduction_pct,
            "cost_saved_usd": cost_saved,
            "latency_diff_ms": int(unopt_state.get("latency_ms", 0)) - int(opt_state.get("latency_ms", 0)),
        },
    }


def _serialize_runtime(rt: AgentSandboxRuntime) -> dict[str, Any]:
    return {
        "id": str(rt.id),
        "tenant_id": str(rt.tenant_id),
        "agent_runtime_id": rt.agent_runtime_id,
        "rental_id": str(rt.rental_id) if rt.rental_id else None,
        "backend_mode": rt.backend_mode,
        "is_container_isolated": rt.is_container_isolated,
        "status": rt.status,
        "container_id": rt.container_id,
        "image_name": rt.image_name,
        "cpu_limit": rt.cpu_limit,
        "memory_limit_mb": rt.memory_limit_mb,
        "timeout_seconds": rt.timeout_seconds,
        "network_mode": rt.network_mode,
        "last_health": rt.last_health_json,
        "execution_logs": (rt.execution_logs_json or [])[-20:],
        "last_started_at": rt.last_started_at.isoformat() if rt.last_started_at else None,
        "last_stopped_at": rt.last_stopped_at.isoformat() if rt.last_stopped_at else None,
        "destroyed_at": rt.destroyed_at.isoformat() if rt.destroyed_at else None,
        "created_at": rt.created_at.isoformat() if rt.created_at else None,
    }


def _serialize_mcp_server(s: McpServerRecord) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "tenant_id": str(s.tenant_id),
        "slug": s.slug,
        "name": s.name,
        "description": s.description,
        "transport": s.transport,
        "command_or_url": s.command_or_url,
        "args": list(s.args_json or []),
        "env_keys": list(s.env_keys_json or []),
        "is_approved": s.is_approved,
        "approval_status": s.approval_status,
        "approved_at": s.approved_at.isoformat() if s.approved_at else None,
        "connection_status": s.connection_status,
        "last_error": s.last_error,
        "discovered_tools": list(s.discovered_tools_json or []),
        "tool_permissions": dict(s.tool_permissions_json or {}),
        "last_checked_at": s.last_checked_at.isoformat() if s.last_checked_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


class CreateRuntimeRequest(BaseModel):
    cpu_limit: Optional[float] = Field(default=None, ge=0.25, le=4.0)
    memory_limit_mb: Optional[int] = Field(default=None, ge=128, le=4096)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=120)
    auto_start: bool = True


class ExecuteRuntimeTaskRequest(BaseModel):
    task_name: str = Field(..., min_length=2, max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=120)


class BrowserInspectRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=1000)
    capture_screenshot: bool = True
    allowlist_override: Optional[list[str]] = None


class RegisterMcpServerRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=80)
    name: str = Field(..., min_length=2, max_length=150)
    transport: Literal["stdio", "sse"] = "stdio"
    command_or_url: str = Field(..., min_length=2, max_length=500)
    args: list[str] = Field(default_factory=list)
    env_keys: list[str] = Field(default_factory=list)
    description: str = Field(default="", max_length=500)


class McpApprovalRequest(BaseModel):
    approved: bool


class McpToolPermissionRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=100)
    allowed: bool
    requires_hitl: bool = False
    allowed_roles: list[str] = Field(default_factory=lambda: ["business_owner", "business_admin"])
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=120)


class McpExecuteRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: Optional[int] = Field(default=None, ge=1, le=120)


@router.get("/monitor")
def get_execution_monitor_snapshot(
    limit: int = Query(default=25, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    return monitor_tracker.build_monitor_snapshot(db, principal.tenant_id, limit=limit)


@router.get("/runtimes")
def list_sandbox_runtimes(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    docker_available, _, docker_detail = sandbox_manager.detect_docker_daemon()
    runtimes = sandbox_manager.list_runtimes(db, principal.tenant_id)
    return {
        "docker_available": docker_available,
        "isolation_notice": docker_detail,
        "runtimes": [_serialize_runtime(r) for r in runtimes],
    }


@router.post("/runtimes", status_code=status.HTTP_201_CREATED)
def create_sandbox_runtime(
    payload: CreateRuntimeRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    rt = sandbox_manager.create_runtime(
        db,
        principal.tenant_id,
        cpu_limit=payload.cpu_limit,
        memory_limit_mb=payload.memory_limit_mb,
        timeout_seconds=payload.timeout_seconds,
        auto_start=payload.auto_start,
    )
    record_audit(
        db,
        tenant_id=principal.tenant_id,
        actor_user_id=principal.user_id,
        action="runtime.created",
        resource_type="sandbox_runtime",
        resource_id=str(rt.id),
        metadata={"backend_mode": rt.backend_mode, "is_container_isolated": rt.is_container_isolated},
    )
    db.commit()
    return _serialize_runtime(rt)


@router.get("/runtimes/{runtime_id}")
def get_sandbox_runtime_status(
    runtime_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        rt = sandbox_manager.get_runtime_status(db, principal.tenant_id, runtime_id)
        db.commit()
        return _serialize_runtime(rt)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/runtimes/{runtime_id}/start")
def start_sandbox_runtime(
    runtime_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        rt = sandbox_manager.start_runtime(db, principal.tenant_id, runtime_id)
        db.commit()
        return _serialize_runtime(rt)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runtimes/{runtime_id}/stop")
def stop_sandbox_runtime(
    runtime_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        rt = sandbox_manager.stop_runtime(db, principal.tenant_id, runtime_id)
        db.commit()
        return _serialize_runtime(rt)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runtimes/{runtime_id}/restart")
def restart_sandbox_runtime(
    runtime_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        rt = sandbox_manager.restart_runtime(db, principal.tenant_id, runtime_id)
        db.commit()
        return _serialize_runtime(rt)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/runtimes/{runtime_id}")
def destroy_sandbox_runtime(
    runtime_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        rt = sandbox_manager.destroy_runtime(db, principal.tenant_id, runtime_id)
        db.commit()
        return _serialize_runtime(rt)
    except SandboxNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/runtimes/{runtime_id}/execute")
def execute_in_sandbox_runtime(
    runtime_id: uuid.UUID,
    payload: ExecuteRuntimeTaskRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        res = sandbox_manager.execute_in_runtime(
            db,
            principal.tenant_id,
            runtime_id,
            task_name=payload.task_name,
            payload=payload.payload,
            timeout_seconds=payload.timeout_seconds,
        )
        db.commit()
        return res
    except SandboxNotFoundError as exc:
        db.commit()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SandboxSecurityError as exc:
        db.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except SandboxTimeoutError as exc:
        db.commit()
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except ValueError as exc:
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        db.commit()
        raise HTTPException(status_code=502, detail=f"Sandbox runtime error: {exc}") from exc


@router.get("/tools")
def list_structured_hr_tools(
    core_only: bool = Query(default=False),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> list[dict[str, Any]]:
    return hr_tool_registry.list_tools_metadata(core_only=core_only)


@router.post("/tools/{tool_id}/execute")
def execute_registered_hr_tool(
    tool_id: str,
    args: dict[str, Any],
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    _enforce_rate_limit(principal, bucket="tool_execute")
    spec = hr_tool_registry.get_spec(tool_id)
    if spec is None and not hr_tool_registry.has_tool(tool_id):
        raise HTTPException(status_code=404, detail=f"HR tool '{tool_id}' is not registered")

    # Respect tenant ToolPermission toggle when tool slug exists in ToolRegistry table
    reg_tool = db.scalar(select(ToolRegistry).where(ToolRegistry.slug == tool_id))
    rental_allowed: list[str] | None = None
    if reg_tool is not None:
        perms = db.scalars(
            select(ToolPermission).where(
                ToolPermission.tenant_id == principal.tenant_id,
                ToolPermission.tool_id == reg_tool.id,
            )
        ).all()
        if perms and not any(p.is_allowed for p in perms):
            rental_allowed = []

    ctx = ToolExecutionContext(
        db=db,
        tenant_id=principal.tenant_id,
        rental_id=None,
        actor_user_id=principal.user_id,
        actor_role=principal.role,
    )
    res = hr_tool_registry.execute(tool_id, ctx, args, rental_allowed_tools=rental_allowed)
    db.commit()
    st = res.get("status")
    if st in {"denied", "blocked_security"}:
        raise HTTPException(status_code=403, detail=res.get("error", "Tool execution blocked"))
    if st == "validation_error":
        raise HTTPException(status_code=422, detail=res.get("error", "Invalid tool arguments"))
    if st == "timeout":
        raise HTTPException(status_code=504, detail=res.get("error", "Tool timed out"))
    if st in {"error", "not_found", "not_configured"}:
        raise HTTPException(status_code=400, detail=res.get("error", "Tool execution error"))
    return res


@router.post("/browser/inspect")
def inspect_url_with_isolated_browser(
    payload: BrowserInspectRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        res = browser_manager.navigate_and_extract(
            tenant_id=principal.tenant_id,
            url=payload.url,
            allowlist=payload.allowlist_override,
            capture_screenshot=payload.capture_screenshot,
        )
        record_audit(
            db,
            tenant_id=principal.tenant_id,
            actor_user_id=principal.user_id,
            action="browser.inspect",
            resource_type="browser_session",
            resource_id=res.get("session_id", "ephemeral"),
            metadata={"hostname": res.get("hostname"), "status_code": res.get("status_code")},
        )
        db.commit()
        return res
    except BrowserSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Browser inspection timed out cleanly before completion.") from exc
    except Exception as exc:
        if "timeout" in type(exc).__name__.lower() or "timed out" in str(exc).lower():
            raise HTTPException(status_code=504, detail="Browser inspection timed out cleanly before completion.") from exc
        safe_msg = re.sub(r"(https?://[^/\s]+:[^@\s]+@|Bearer\s+\S+)", "[REDACTED]", str(exc))[:220]
        raise HTTPException(status_code=502, detail=f"Browser inspection failed: {safe_msg}") from exc


@router.get("/mcp/servers")
def list_mcp_servers(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    servers = mcp_manager.list_servers(db, principal.tenant_id)
    logs = mcp_manager.list_logs(db, principal.tenant_id, limit=30)
    return {
        "servers": [_serialize_mcp_server(s) for s in servers],
        "execution_logs": [
            {
                "id": str(m.id),
                "server_id": str(m.server_id),
                "tool_name": m.tool_name,
                "status": m.status,
                "duration_ms": m.duration_ms,
                "error_message": m.error_message,
                "request_summary": m.request_summary_json,
                "response_summary": m.response_summary_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in logs
        ],
    }


@router.post("/mcp/servers", status_code=status.HTTP_201_CREATED)
def register_mcp_server(
    payload: RegisterMcpServerRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        row = mcp_manager.register_server(
            db,
            principal.tenant_id,
            actor_user_id=principal.user_id,
            slug=payload.slug,
            name=payload.name,
            transport=payload.transport,
            command_or_url=payload.command_or_url,
            args=payload.args,
            env_keys=payload.env_keys,
            description=payload.description,
        )
        db.commit()
        return _serialize_mcp_server(row)
    except McpSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except McpValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/mcp/servers/{server_id}/approval")
def set_mcp_server_approval(
    server_id: uuid.UUID,
    payload: McpApprovalRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        row = mcp_manager.set_server_approval(
            db,
            principal.tenant_id,
            server_id,
            approved=payload.approved,
            actor_user_id=principal.user_id,
        )
        db.commit()
        return _serialize_mcp_server(row)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/mcp/servers/{server_id}/discover")
def discover_mcp_server_tools(
    server_id: uuid.UUID,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        res = mcp_manager.check_connection_and_discover(db, principal.tenant_id, server_id)
        db.commit()
        return res
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except McpSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.patch("/mcp/servers/{server_id}/permissions")
def update_mcp_tool_permission(
    server_id: uuid.UUID,
    payload: McpToolPermissionRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        row = mcp_manager.configure_tool_permissions(
            db,
            principal.tenant_id,
            server_id,
            tool_name=payload.tool_name,
            allowed=payload.allowed,
            requires_hitl=payload.requires_hitl,
            allowed_roles=payload.allowed_roles,
            timeout_seconds=payload.timeout_seconds,
            actor_user_id=principal.user_id,
        )
        db.commit()
        return _serialize_mcp_server(row)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/mcp/servers/{server_id}/execute")
def execute_mcp_server_tool(
    server_id: uuid.UUID,
    payload: McpExecuteRequest,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> dict[str, Any]:
    try:
        res = mcp_manager.execute_tool(
            db,
            principal.tenant_id,
            server_id,
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            actor_user_id=principal.user_id,
            actor_role=principal.role,
            timeout_seconds=payload.timeout_seconds,
        )
        db.commit()
        return res
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except McpSecurityError as exc:
        db.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except McpValidationError as exc:
        db.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        db.commit()
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
