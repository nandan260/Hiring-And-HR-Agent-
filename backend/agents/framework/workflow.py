"""Shared LangGraph multi-stage agent execution workflow with strict tenant, RBAC, quota, and HITL gates."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
import time
from typing import Any, Callable, Optional
import uuid

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import (
    AgentCatalog,
    AgentConfiguration,
    AgentRental,
    AgentSandboxRuntime,
    AuditLog,
    ExecutionLog,
    OrganizationMember,
    TokenUsage,
    ToolPermission,
    ToolRegistry,
)
from app.runtime.monitor import monitor_tracker
from app.runtime.redaction import redact_secrets_in_text, sanitize_structured_payload

from .base_agent import BaseSpecializedAgent
from .classifier import HR_WORKFLOW_DISPLAY_NAMES, classify_domain_boundary, classify_intent_detailed
from .guardrails import check_hr_safety_input, validate_input_safety
from .optimizer import optimizer_execution_scope, tenant_response_cache
from .state import AgentExecutionState, TraceStep
from .tools import AgentToolBox, ToolContext

# Role-based access policy per HR workflow.
# Regular employees (business_employee) may invoke Employee Policy Support self-service;
# Recruiting, Shortlisting, JD Creation, Interview Scheduling, Onboarding & Analytics require admin/owner roles.
WORKFLOW_ALLOWED_ROLES: dict[str, set[str]] = {
    "hr-policy-support": {"platform_admin", "business_owner", "business_admin", "business_employee"},
    "recruitment-screening": {"platform_admin", "business_owner", "business_admin"},
    "jd-generator": {"platform_admin", "business_owner", "business_admin"},
    "candidate-shortlisting": {"platform_admin", "business_owner", "business_admin"},
    "interview-scheduling": {"platform_admin", "business_owner", "business_admin"},
    "employee-onboarding": {"platform_admin", "business_owner", "business_admin"},
    "hr-analytics": {"platform_admin", "business_owner", "business_admin"},
}


def _timed_node(step_name: str):
    """Wrap a LangGraph node function to capture structured TraceStep timings."""

    def decorator(fn: Callable[[AgentExecutionState, RunnableConfig], dict[str, Any]]):
        @wraps(fn)
        def wrapper(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
            t0 = time.perf_counter()
            update = fn(state, config)
            elapsed_ms = max(1, int((time.perf_counter() - t0) * 1000))
            traces = list(state.get("trace_steps", []))
            if "trace_step" in update:
                step_info = update.pop("trace_step")
                traces.append(
                    TraceStep(
                        step=step_name,
                        status=step_info.get("status", "ok"),
                        duration_ms=elapsed_ms,
                        detail=step_info.get("detail", ""),
                    )
                )
            else:
                traces.append(
                    TraceStep(step=step_name, status="ok", duration_ms=elapsed_ms, detail="completed")
                )
            update["trace_steps"] = traces
            return update

        return wrapper

    return decorator


def _get_runtime(config: RunnableConfig) -> dict[str, Any]:
    return config.get("configurable", {})


def _get_active_agent(state: AgentExecutionState, config: RunnableConfig) -> BaseSpecializedAgent:
    cfg = _get_runtime(config)
    routed_id = state.get("routed_agent_id")
    available: dict[str, BaseSpecializedAgent] = cfg.get("available_agents") or {}
    if routed_id and routed_id in available:
        return available[routed_id]
    return cfg["agent"]


def _make_tool_context(state: AgentExecutionState, config: RunnableConfig) -> ToolContext:
    cfg = _get_runtime(config)
    return ToolContext(
        db=cfg["db"],
        tenant_id=uuid.UUID(state["tenant_id"]),
        rental_id=uuid.UUID(state["rental_id"]) if state.get("rental_id") else None,
        actor_user_id=uuid.UUID(state["actor_user_id"]) if state.get("actor_user_id") else None,
        actor_role=state.get("actor_role", "business_employee"),
        blind_screening_mode=bool(state.get("blind_screening_mode", False)),
        strict_pii_masking=bool(state.get("strict_pii_masking", True)),
    )


def _check_and_lock_monthly_quota(
    db: Session,
    *,
    tenant_uuid: uuid.UUID,
    rental_uuid: Optional[uuid.UUID],
    estimated_tokens: int,
) -> tuple[bool, Optional[int], int, str]:
    """
    Concurrency-safe PostgreSQL monthly token quota check.
    Acquires deterministic row-level FOR UPDATE locks on tenant AgentConfiguration rows
    ordered by primary key so concurrent requests serialize cleanly until TokenUsage persists.
    """
    cfg_rows = db.scalars(
        select(AgentConfiguration)
        .where(AgentConfiguration.tenant_id == tenant_uuid)
        .order_by(AgentConfiguration.id)
        .with_for_update()
    ).all()

    if not cfg_rows:
        return True, None, 0, ""

    now_utc = datetime.now(timezone.utc)
    month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    target_cfg = next((c for c in cfg_rows if rental_uuid and c.rental_id == rental_uuid), None)

    if rental_uuid and target_cfg is not None:
        rental_used = int(
            db.scalar(
                select(func.coalesce(func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens), 0)).where(
                    TokenUsage.tenant_id == tenant_uuid,
                    TokenUsage.rental_id == rental_uuid,
                    TokenUsage.created_at >= month_start,
                )
            )
            or 0
        )
        rental_limit = int(target_cfg.monthly_token_quota)
        if rental_limit <= 0 or (rental_used + estimated_tokens) > rental_limit:
            return (
                False,
                rental_limit,
                rental_used,
                (
                    f"Monthly token quota exceeded ({rental_used:,} / {rental_limit:,} tokens used this month). "
                    "Increase the monthly token quota in Settings before running additional tasks."
                ),
            )

        # Unified workspace-wide quota cap (set via /hr-agent/settings) if configured
        extra = target_cfg.extra_settings or {}
        unified_limit = extra.get("unified_quota_limit")
        if unified_limit is not None:
            tenant_used = int(
                db.scalar(
                    select(func.coalesce(func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens), 0)).where(
                        TokenUsage.tenant_id == tenant_uuid,
                        TokenUsage.created_at >= month_start,
                    )
                )
                or 0
            )
            cap = int(unified_limit)
            if cap <= 0 or (tenant_used + estimated_tokens) > cap:
                return (
                    False,
                    cap,
                    tenant_used,
                    (
                        f"Monthly workspace token quota exceeded ({tenant_used:,} / {cap:,} tokens used this month). "
                        "Adjust your HireFlow AI monthly token quota in Settings to continue."
                    ),
                )
        return True, rental_limit, rental_used, ""

    return True, None, 0, ""


@_timed_node("authenticate")
def node_authenticate(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    actor_user_id = state.get("actor_user_id")
    tenant_id = state.get("tenant_id")
    if not actor_user_id or not tenant_id:
        return {
            "principal_verified": False,
            "classifier_result": "blocked_permission",
            "execution_status": "blocked",
            "rejection_reason": "Authenticated user and tenant context are required before agent execution.",
            "trace_step": {"status": "blocked", "detail": "missing principal or tenant_id"},
        }
    return {
        "principal_verified": True,
        "trace_step": {"status": "ok", "detail": f"verified role={state.get('actor_role', 'member')}"},
    }


@_timed_node("validate_tenant")
def node_validate_tenant(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    if not state.get("principal_verified"):
        return {
            "permissions_ok": False,
            "trace_step": {"status": "skipped", "detail": "principal not verified"},
        }

    cfg = _get_runtime(config)
    db: Session = cfg["db"]
    agent = _get_active_agent(state, config)

    tenant_uuid = uuid.UUID(state["tenant_id"])
    user_uuid = uuid.UUID(state["actor_user_id"])

    member = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.tenant_id == tenant_uuid,
            OrganizationMember.user_id == user_uuid,
        )
    ).scalar_one_or_none()
    if member is None:
        return {
            "permissions_ok": False,
            "classifier_result": "blocked_permission",
            "execution_status": "blocked",
            "rejection_reason": "Tenant membership verification failed: cross-tenant access is denied.",
            "trace_step": {"status": "blocked", "detail": "user is not an active member of tenant"},
        }

    rental_allowed_tools = list(agent.allowed_tools)
    custom_persona = ""
    blind_screening = False
    strict_pii = True
    require_hitl = bool(agent.tool_permissions.hitl_required_tools)
    rental_status = "active"
    model_tier_override = None

    if state.get("rental_id"):
        rental_uuid = uuid.UUID(state["rental_id"])
        rental = db.execute(
            select(AgentRental).where(
                AgentRental.id == rental_uuid,
                AgentRental.tenant_id == tenant_uuid,
            )
        ).scalar_one_or_none()
        if rental is None:
            return {
                "permissions_ok": False,
                "classifier_result": "blocked_permission",
                "execution_status": "blocked",
                "rejection_reason": "Workflow configuration not found in authenticated tenant workspace.",
                "trace_step": {"status": "blocked", "detail": "rental_id does not belong to tenant"},
            }
        rental_status = rental.status
        if rental.status != "active":
            return {
                "permissions_ok": False,
                "classifier_result": "blocked_permission",
                "execution_status": "blocked",
                "rental_status": rental.status,
                "rejection_reason": f"Workflow is currently '{rental.status}'. Activate it to run tasks.",
                "trace_step": {"status": "blocked", "detail": f"rental status={rental.status}"},
            }

        agent_cfg = db.execute(
            select(AgentConfiguration).where(
                AgentConfiguration.tenant_id == tenant_uuid,
                AgentConfiguration.rental_id == rental_uuid,
            )
        ).scalar_one_or_none()
        if agent_cfg is not None:
            custom_persona = agent_cfg.custom_persona_prompt or ""
            blind_screening = bool(agent_cfg.blind_screening_mode)
            strict_pii = bool(agent_cfg.strict_pii_masking)
            require_hitl = bool(agent_cfg.require_hitl_approval)
            model_tier_override = agent_cfg.model_routing_tier

        perm_rows = db.execute(
            select(ToolPermission, ToolRegistry)
            .join(ToolRegistry, ToolRegistry.id == ToolPermission.tool_id)
            .where(
                ToolPermission.tenant_id == tenant_uuid,
                ToolPermission.rental_id == rental_uuid,
            )
        ).all()
        if perm_rows:
            disabled_slugs = {reg.slug for perm, reg in perm_rows if not perm.is_allowed}
            rental_allowed_tools = [t for t in rental_allowed_tools if t not in disabled_slugs]

    return {
        "permissions_ok": True,
        "rental_status": rental_status,
        "rental_allowed_tools": rental_allowed_tools,
        "custom_persona_prompt": custom_persona,
        "blind_screening_mode": blind_screening,
        "strict_pii_masking": strict_pii,
        "require_hitl_approval": require_hitl,
        "model_tier_override": model_tier_override,
        "trace_step": {"status": "ok", "detail": f"tenant verified, {len(rental_allowed_tools)} tools active"},
    }


@_timed_node("classify_intent")
def node_classify_intent(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    if not state.get("permissions_ok"):
        return {"trace_step": {"status": "skipped", "detail": "tenant validation failed"}}

    agent = _get_active_agent(state, config)
    raw_prompt = state.get("user_input", "")
    flags = list(state.get("guardrail_flags") or [])

    safe_ok, safe_msg, input_flags = validate_input_safety(
        raw_prompt,
        max_input_tokens=agent.execution_limits.max_input_tokens,
        structured_input=state.get("structured_input"),
    )
    if not safe_ok:
        flags.extend(input_flags)
        return {
            "input_valid": False,
            "domain_allowed": False,
            "classifier_result": "invalid_input",
            "execution_status": "failed",
            "guardrail_flags": list(dict.fromkeys(flags)),
            "rejection_reason": safe_msg,
            "trace_step": {"status": "failed", "detail": safe_msg[:120]},
        }

    intent = classify_intent_detailed(
        raw_prompt,
        agent.agent_id,
        structured_input=state.get("structured_input"),
        conversation_history=state.get("conversation_history"),
        allow_llm_fallback=True,
    )
    intent_dict = intent.to_dict()

    if intent.is_injection:
        flags.append("prompt_injection_blocked")
        return {
            "intent_label": intent.intent_label,
            "intent_analysis": intent_dict,
            "domain_allowed": False,
            "classifier_result": "blocked_injection",
            "execution_status": "blocked",
            "guardrail_flags": list(dict.fromkeys(flags)),
            "rejection_reason": (
                "Prompt injection or system/permission extraction attempt detected and blocked. "
                "System prompts, permissions, and tenant boundaries cannot be overridden."
            ),
            "trace_step": {"status": "blocked", "detail": "prompt_injection detected"},
        }

    if intent.is_bias_attempt or intent.user_intent == "blocked_auto_reject":
        flags.append(intent.user_intent)
        return {
            "intent_label": intent.intent_label,
            "intent_analysis": intent_dict,
            "domain_allowed": False,
            "classifier_result": intent.user_intent,
            "execution_status": "rejected" if intent.user_intent == "blocked_policy_fairness" else "blocked",
            "guardrail_flags": list(dict.fromkeys(flags)),
            "rejection_reason": intent.requested_task
            or "Blocked by HR Fairness & Human Review safety policy.",
            "trace_step": {"status": "rejected" if intent.user_intent == "blocked_policy_fairness" else "blocked", "detail": f"hr_safety_blocked ({intent.user_intent})"},
        }

    if intent.needs_clarification:
        return {
            "intent_label": intent.intent_label,
            "intent_analysis": intent_dict,
            "domain_allowed": True,
            "classifier_result": "needs_clarification",
            "execution_status": "needs_clarification",
            "clarification_questions": intent.clarification_questions,
            "rejection_reason": "Please provide brief clarification so HireFlow AI can execute accurately.",
            "trace_step": {"status": "ok", "detail": f"clarification requested ({intent.hr_workflow})"},
        }

    return {
        "intent_label": intent.intent_label,
        "intent_analysis": intent_dict,
        "trace_step": {
            "status": "ok",
            "detail": f"intent={intent.intent_label}, risk={intent.risk_level}, via={intent.classifier_method}",
        },
    }


@_timed_node("classify_domain")
def node_classify_domain(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    if state.get("classifier_result") in {"blocked_injection", "blocked_permission"}:
        return {"domain_allowed": False, "trace_step": {"status": "skipped", "detail": "already blocked"}}

    cfg = _get_runtime(config)
    agent = _get_active_agent(state, config)
    available: dict[str, BaseSpecializedAgent] = cfg.get("available_agents") or {}

    domain_res = classify_domain_boundary(
        state.get("user_input", ""),
        agent.agent_id,
        agent.domain,
        agent.guardrails,
        structured_input=state.get("structured_input"),
        conversation_history=state.get("conversation_history"),
    )
    if not domain_res.allowed:
        return {
            "domain_allowed": False,
            "classifier_result": domain_res.classifier_result,
            "execution_status": "blocked" if domain_res.classifier_result == "blocked_injection" else "rejected",
            "rejection_reason": domain_res.reason,
            "suggested_category": domain_res.suggested_category,
            "trace_step": {
                "status": "rejected",
                "detail": f"{domain_res.classifier_result} ({domain_res.suggested_category or 'out_of_scope'})",
            },
        }

    routed_slug = domain_res.suggested_agent_slug
    updates: dict[str, Any] = {
        "domain_allowed": True,
        "classifier_result": "in_domain",
    }
    if routed_slug and routed_slug != agent.agent_id and routed_slug in available:
        updates["routed_agent_id"] = routed_slug
        updates["routing_reason"] = domain_res.reason
        updates["trace_step"] = {
            "status": "ok",
            "detail": f"routed cross-HR {agent.agent_id} -> {routed_slug}",
        }
    else:
        updates["routed_agent_id"] = agent.agent_id
        updates["trace_step"] = {"status": "ok", "detail": f"in_domain for {agent.agent_id}"}
    return updates


@_timed_node("check_permissions")
def node_check_permissions(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    cfg = _get_runtime(config)
    db: Session = cfg["db"]
    agent = _get_active_agent(state, config)
    actor_role = state.get("actor_role", "business_employee")
    allowed_set = list(state.get("rental_allowed_tools") or agent.allowed_tools)

    # Refresh rental/tool permissions if cross-HR routing switched workflows inside the graph
    routed_rental_id = state.get("rental_id")
    custom_persona = state.get("custom_persona_prompt", "")
    blind_screening = bool(state.get("blind_screening_mode", False))
    strict_pii = bool(state.get("strict_pii_masking", True))
    require_hitl = bool(state.get("require_hitl_approval", bool(agent.tool_permissions.hitl_required_tools)))
    model_tier_override = state.get("model_tier_override")

    tenant_uuid = uuid.UUID(state["tenant_id"])
    if state.get("routed_agent_id") and state.get("routed_agent_id") != state.get("requested_agent_id"):
        target_rental = db.execute(
            select(AgentRental)
            .join(AgentCatalog, AgentCatalog.id == AgentRental.agent_id)
            .where(
                AgentRental.tenant_id == tenant_uuid,
                AgentCatalog.slug == agent.agent_id,
                AgentRental.status == "active",
            )
            .order_by(AgentRental.created_at.desc())
        ).scalar_one_or_none()
        allowed_set = list(agent.allowed_tools)
        if target_rental is not None:
            routed_rental_id = str(target_rental.id)
            target_cfg = db.execute(
                select(AgentConfiguration).where(
                    AgentConfiguration.tenant_id == tenant_uuid,
                    AgentConfiguration.rental_id == target_rental.id,
                )
            ).scalar_one_or_none()
            if target_cfg is not None:
                custom_persona = target_cfg.custom_persona_prompt or ""
                blind_screening = bool(target_cfg.blind_screening_mode)
                strict_pii = bool(target_cfg.strict_pii_masking)
                require_hitl = bool(target_cfg.require_hitl_approval)
                model_tier_override = target_cfg.model_routing_tier
            perm_rows = db.execute(
                select(ToolPermission, ToolRegistry)
                .join(ToolRegistry, ToolRegistry.id == ToolPermission.tool_id)
                .where(
                    ToolPermission.tenant_id == tenant_uuid,
                    ToolPermission.rental_id == target_rental.id,
                )
            ).all()
            if perm_rows:
                disabled_slugs = {reg.slug for perm, reg in perm_rows if not perm.is_allowed}
                allowed_set = [t for t in allowed_set if t not in disabled_slugs]

    # Strict workflow-level RBAC check
    allowed_roles = WORKFLOW_ALLOWED_ROLES.get(
        agent.agent_id, {"platform_admin", "business_owner", "business_admin"}
    )
    if actor_role not in allowed_roles:
        wf_name = HR_WORKFLOW_DISPLAY_NAMES.get(agent.agent_id, agent.agent_name)
        return {
            "permissions_ok": False,
            "quota_ok": False,
            "rental_id": routed_rental_id,
            "classifier_result": "blocked_permission",
            "execution_status": "blocked",
            "rejection_reason": (
                f"Access denied: workspace role '{actor_role}' is not permitted to invoke the "
                f"'{wf_name}' workflow. Employees may use Employee Policy Support; Recruitment, "
                "Job Descriptions, Shortlisting, Interview Scheduling, Onboarding, and Analytics "
                "require Business Admin or Owner access."
            ),
            "trace_step": {"status": "blocked", "detail": f"role '{actor_role}' denied for {agent.agent_id}"},
        }

    # Concurrency-safe monthly_token_quota check (row-level FOR UPDATE lock)
    approx_input_tokens = max(1, len(state.get("user_input", "")) // 4)
    rental_uuid = uuid.UUID(routed_rental_id) if routed_rental_id else None
    quota_ok, quota_limit, quota_used, quota_msg = _check_and_lock_monthly_quota(
        db,
        tenant_uuid=tenant_uuid,
        rental_uuid=rental_uuid,
        estimated_tokens=approx_input_tokens,
    )
    if not quota_ok:
        return {
            "permissions_ok": False,
            "quota_ok": False,
            "quota_limit": quota_limit,
            "quota_used": quota_used,
            "rental_id": routed_rental_id,
            "classifier_result": "blocked_quota",
            "execution_status": "blocked",
            "rejection_reason": quota_msg,
            "trace_step": {"status": "blocked", "detail": f"quota exceeded ({quota_used}/{quota_limit})"},
        }

    return {
        "permissions_ok": True,
        "quota_ok": True,
        "quota_limit": quota_limit,
        "quota_used": quota_used,
        "rental_id": routed_rental_id,
        "rental_allowed_tools": allowed_set,
        "custom_persona_prompt": custom_persona,
        "blind_screening_mode": blind_screening,
        "strict_pii_masking": strict_pii,
        "require_hitl_approval": require_hitl,
        "model_tier_override": model_tier_override,
        "trace_step": {"status": "ok", "detail": f"rbac & quota ok ({len(allowed_set)} tools enabled)"},
    }


@_timed_node("validate_input")
def node_validate_input(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    agent = _get_active_agent(state, config)
    raw_prompt = state.get("user_input", "")
    flags = list(state.get("guardrail_flags") or [])

    safe_ok, safe_msg, input_flags = validate_input_safety(
        raw_prompt,
        max_input_tokens=agent.execution_limits.max_input_tokens,
        structured_input=state.get("structured_input"),
    )
    if not safe_ok:
        flags.extend(input_flags)
        return {
            "input_valid": False,
            "classifier_result": "invalid_input",
            "execution_status": "failed",
            "guardrail_flags": list(dict.fromkeys(flags)),
            "rejection_reason": safe_msg,
            "trace_step": {"status": "failed", "detail": safe_msg[:120]},
        }

    hr_ok, hr_flag, hr_msg = check_hr_safety_input(raw_prompt, state.get("structured_input"))
    if not hr_ok:
        flags.append(hr_flag)
        return {
            "input_valid": False,
            "classifier_result": hr_flag,
            "execution_status": "blocked",
            "guardrail_flags": list(dict.fromkeys(flags)),
            "rejection_reason": hr_msg,
            "trace_step": {"status": "blocked", "detail": hr_flag},
        }

    try:
        parsed = agent.validate_structured_input(
            raw_prompt,
            structured_input=state.get("structured_input"),
            attachments=state.get("attachments"),
        )
        return {
            "input_valid": True,
            "structured_input": parsed.model_dump(mode="json"),
            "trace_step": {"status": "ok", "detail": f"validated schema {agent.input_schema.__name__}"},
        }
    except ValidationError as exc:
        return {
            "input_valid": False,
            "classifier_result": "invalid_input",
            "execution_status": "failed",
            "rejection_reason": f"Input validation failed: {exc.errors()[0].get('msg', str(exc))}",
            "trace_step": {"status": "failed", "detail": "schema validation error"},
        }


@_timed_node("select_agent")
def node_select_agent(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    agent = _get_active_agent(state, config)
    system_prompt = agent.load_system_prompt(state.get("custom_persona_prompt", ""))
    mem = agent.build_memory_context(state.get("conversation_history", []))
    return {
        "selected_agent_id": agent.agent_id,
        "selected_agent_version": agent.agent_version,
        "system_prompt_loaded": system_prompt,
        "conversation_summary": mem.get("summary", ""),
        "trace_step": {"status": "ok", "detail": f"selected {agent.agent_id}@{agent.agent_version}"},
    }


@_timed_node("execute_agent")
def node_execute_agent(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    agent = _get_active_agent(state, config)
    parsed_input = agent.validate_structured_input(
        state.get("user_input", ""),
        structured_input=state.get("structured_input"),
        attachments=state.get("attachments"),
    )
    ctx = _make_tool_context(state, config)
    planned = agent.select_tools(parsed_input, state, ctx)[: agent.execution_limits.max_tool_calls]
    return {
        "planned_tools": planned,
        "trace_step": {"status": "ok", "detail": f"planned {len(planned)} tool calls"},
    }


@_timed_node("execute_tools")
def node_execute_tools(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    cfg = _get_runtime(config)
    agent = _get_active_agent(state, config)
    toolbox: AgentToolBox = cfg["toolbox"]
    ctx = _make_tool_context(state, config)
    planned = state.get("planned_tools", [])
    rental_allowed = state.get("rental_allowed_tools")
    max_tools = max(1, int(agent.execution_limits.max_tool_calls))
    timeout_sec = max(1, int(agent.execution_limits.timeout_seconds))
    started_mono = float(state.get("workflow_started_at_monotonic") or time.perf_counter())
    flags = list(state.get("guardrail_flags") or [])

    results: list[dict[str, Any]] = []
    for idx, item in enumerate(planned):
        if idx >= max_tools:
            flags.append("tool_call_cap_enforced")
            break
        if (time.perf_counter() - started_mono) > timeout_sec:
            flags.append("execution_timeout_enforced")
            results.append(
                {
                    "tool": item.get("tool", "unknown"),
                    "status": "timeout",
                    "duration_ms": 0,
                    "risk_level": "low",
                    "error": f"Execution timeout cap ({timeout_sec}s) reached; remaining tool calls aborted.",
                }
            )
            break
        slug = item.get("tool", "")
        args = item.get("args", {})
        res = toolbox.run_tool(
            slug=slug,
            ctx=ctx,
            args=args,
            agent_allowed_tools=agent.allowed_tools,
            rental_allowed_tools=rental_allowed,
        )
        if res.get("status") == "timeout":
            flags.append("tool_execution_timeout")
        elif res.get("status") == "error":
            flags.append("tool_execution_error")
        results.append(res)

    monitor_tracker.update_run(
        cfg.get("monitor_run_id"),
        current_workflow=agent.agent_id,
        tool_calls=[
            {"tool": r.get("tool"), "status": r.get("status"), "duration_ms": r.get("duration_ms", 0)}
            for r in results
        ],
    )

    return {
        "tool_results": results,
        "guardrail_flags": list(dict.fromkeys(flags)),
        "trace_step": {"status": "ok", "detail": f"executed {len(results)} tool calls"},
    }


@_timed_node("validate_output")
def node_validate_output(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    settings = get_settings()
    agent = _get_active_agent(state, config)
    parsed_input = agent.validate_structured_input(
        state.get("user_input", ""),
        structured_input=state.get("structured_input"),
        attachments=state.get("attachments"),
    )
    ctx = _make_tool_context(state, config)
    tool_results = state.get("tool_results", [])
    memory_ctx = agent.build_memory_context(state.get("conversation_history", []))
    opt_enabled = bool(state.get("enable_optimization", settings.ENABLE_CONTEXT_OPTIMIZATION))

    opt_scope_data: dict[str, Any] = {
        "tenant_id": state.get("tenant_id", ""),
        "actor_role": state.get("actor_role", "business_admin"),
        "workflow_slug": agent.agent_id,
        "optimization_enabled": opt_enabled,
        "blind_screening_mode": bool(state.get("blind_screening_mode", False)),
        "strict_pii_masking": bool(state.get("strict_pii_masking", False)),
        "model_tier_override": state.get("model_tier_override"),
        "baseline_input_tokens": 0,
        "optimized_input_tokens": 0,
        "cached_tokens": 0,
        "optimization_methods_used": [],
        "guardrail_flags": [],
        "model_tier_selected": "tier_0_rule",
        "cache_hit": False,
    }
    with optimizer_execution_scope(opt_scope_data) as opt_scope:
        raw_output_model, llm_meta = agent.synthesize_output(
            parsed_input=parsed_input,
            tool_results=tool_results,
            memory_ctx=memory_ctx,
            state=state,
            ctx=ctx,
        )

    validated = agent.output_schema.model_validate(raw_output_model)
    validated_dict = validated.model_dump(mode="json")

    actual_in_tok = int(llm_meta.get("input_tokens", 0))
    baseline_tok = int(opt_scope.get("baseline_input_tokens") or actual_in_tok)
    cached_tok = int(opt_scope.get("cached_tokens") if opt_scope.get("cache_hit") else llm_meta.get("cached_tokens", 0))
    methods_used = list(opt_scope.get("optimization_methods_used") or [])
    merged_flags = list(dict.fromkeys(list(state.get("guardrail_flags") or []) + list(opt_scope.get("guardrail_flags") or [])))
    saved_tok = max(0, baseline_tok - actual_in_tok) if opt_enabled else 0
    reduction_pct = round((saved_tok / baseline_tok) * 100.0, 2) if (opt_enabled and baseline_tok > 0) else 0.0

    status_val = "paused_hitl" if validated_dict.get("hitl_requests") else "completed"
    return {
        "agent_raw_output": validated_dict,
        "validated_output": validated_dict,
        "citations": list(validated_dict.get("citations", [])),
        "charts": list(validated_dict.get("charts", [])),
        "hitl_requests": list(validated_dict.get("hitl_requests", [])),
        "execution_status": status_val,
        "baseline_input_tokens": baseline_tok,
        "input_tokens": actual_in_tok,
        "cached_tokens": cached_tok,
        "output_tokens": int(llm_meta.get("output_tokens", 0)),
        "estimated_cost_usd": float(llm_meta.get("estimated_cost_usd", 0.0)),
        "model_used": llm_meta.get("model_used", "deterministic"),
        "llm_provider_used": llm_meta.get("provider_used", llm_meta.get("provider", "deterministic")),
        "optimization_methods_used": methods_used,
        "optimization_telemetry": {
            "optimization_enabled": opt_enabled,
            "baseline_input_tokens": baseline_tok,
            "optimized_input_tokens": actual_in_tok,
            "cached_tokens": cached_tok,
            "tokens_saved": saved_tok,
            "reduction_percent": reduction_pct,
            "methods_used": methods_used,
            "model_tier": opt_scope.get("model_tier_selected", "tier_0_rule"),
            "cache_hit": bool(opt_scope.get("cache_hit", False)),
        },
        "guardrail_flags": merged_flags,
        "trace_step": {"status": "ok", "detail": f"validated {agent.output_schema.__name__}"},
    }


@_timed_node("check_guardrails")
def node_check_guardrails(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    cfg = _get_runtime(config)
    db: Session = cfg["db"]
    agent = _get_active_agent(state, config)
    parsed_input = agent.validate_structured_input(
        state.get("user_input", ""),
        structured_input=state.get("structured_input"),
        attachments=state.get("attachments"),
    )
    validated_obj = agent.output_schema.model_validate(state.get("validated_output") or {})
    checked_obj, notes, passed = agent.apply_domain_guardrails(
        validated_obj,
        parsed_input,
        state.get("tool_results", []),
        blind_mode=bool(state.get("blind_screening_mode", False)),
        strict_pii_masking=bool(state.get("strict_pii_masking", False)),
        actor_role=state.get("actor_role", "business_admin"),
    )
    validated_dict = checked_obj.model_dump(mode="json")

    if not passed:
        return {
            "guardrail_passed": False,
            "guardrail_notes": notes,
            "classifier_result": "blocked_policy_fairness",
            "execution_status": "blocked",
            "rejection_reason": notes[0] if notes else "Blocked by HR domain output guardrail.",
            "validated_output": validated_dict,
            "trace_step": {"status": "blocked", "detail": notes[0] if notes else "guardrail failed"},
        }

    # Persist real HITL approval queue records whenever an agent requests external writes
    hitl_items = list(validated_dict.get("hitl_requests") or [])
    persisted_hitl: list[dict[str, Any]] = []
    if hitl_items and state.get("tenant_id") and state.get("rental_id"):
        from app.db.models import HitlApproval

        tenant_uuid = uuid.UUID(state["tenant_id"])
        rental_uuid = uuid.UUID(state["rental_id"])
        conv_uuid = uuid.UUID(cfg["conversation_id"]) if cfg.get("conversation_id") else None
        actor_uuid = uuid.UUID(state["actor_user_id"]) if state.get("actor_user_id") else None
        for item in hitl_items:
            row = HitlApproval(
                tenant_id=tenant_uuid,
                rental_id=rental_uuid,
                conversation_id=conv_uuid,
                requested_by_user_id=actor_uuid,
                agent_slug=agent.agent_id,
                action_type=str(item.get("action_type", "external_write")),
                title=str(item.get("title", "HITL Approval Required"))[:240],
                summary=str(item.get("summary", "Pending human review"))[:1000],
                payload_json=dict(item.get("payload", {})),
                status="pending",
            )
            db.add(row)
            db.flush()
            copy_item = dict(item)
            copy_item["approval_id"] = str(row.id)
            copy_item["status"] = "pending"
            persisted_hitl.append(copy_item)

    if persisted_hitl:
        notes.append(f"Queued {len(persisted_hitl)} external write action(s) into Human-in-the-Loop approval inbox.")

    return {
        "guardrail_passed": True,
        "guardrail_notes": notes,
        "hitl_requests": persisted_hitl or hitl_items,
        "validated_output": validated_dict,
        "trace_step": {"status": "ok", "detail": f"guardrails passed ({len(notes)} notes)"},
    }


@_timed_node("build_response")
def node_build_response(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    agent = _get_active_agent(state, config)
    classifier_result = state.get("classifier_result", "in_domain")

    if classifier_result == "needs_clarification":
        questions = list(state.get("clarification_questions") or [])
        lines = ["**Clarification Needed to Proceed**", "", "Before running HR tools, could you clarify:"]
        for idx, q in enumerate(questions, start=1):
            lines.append(f"{idx}. {q}")
        return {
            "final_response_text": "\n".join(lines),
            "trace_step": {"status": "ok", "detail": "clarification questions returned"},
        }

    if classifier_result != "in_domain" or not state.get("guardrail_passed", True):
        reason = state.get("rejection_reason") or "Request declined by HireFlow AI policy or domain guard."
        lines = [f"**Request Declined ({classifier_result})**", "", reason]
        if classifier_result not in {"blocked_permission", "blocked_quota", "blocked_injection"}:
            lines.append("")
            lines.append(
                "HireFlow AI handles strictly Hiring & HR operations (Recruitment Screening, Job Descriptions, "
                "Candidate Shortlisting, Interview Scheduling, Employee Onboarding, HR Policy Support, and HR Analytics)."
            )
        return {
            "final_response_text": "\n".join(lines),
            "trace_step": {"status": "ok", "detail": f"formatted decline response ({classifier_result})"},
        }

    validated = agent.output_schema.model_validate(state["validated_output"])
    reply_md = agent.format_markdown_reply(validated)
    return {
        "final_response_text": reply_md,
        "trace_step": {"status": "ok", "detail": "formatted structured markdown reply"},
    }


@_timed_node("log_execution")
def node_log_execution(state: AgentExecutionState, config: RunnableConfig) -> dict[str, Any]:
    cfg = _get_runtime(config)
    db: Session = cfg["db"]
    persist_telemetry: bool = bool(cfg.get("persist_telemetry", True))
    started_ms: float = float(cfg.get("started_at_ms", time.perf_counter() * 1000))
    total_latency_ms = max(1, int(time.perf_counter() * 1000 - started_ms))

    exec_log_id: Optional[str] = None
    if persist_telemetry and state.get("tenant_id") and state.get("rental_id"):
        tenant_uuid = uuid.UUID(state["tenant_id"])
        rental_uuid = uuid.UUID(state["rental_id"])
        conv_uuid = uuid.UUID(cfg["conversation_id"]) if cfg.get("conversation_id") else None
        actor_uuid = uuid.UUID(state["actor_user_id"]) if state.get("actor_user_id") else None
        raw_tool_results = list(state.get("tool_results", []))
        tool_names = [t.get("tool", "") for t in raw_tool_results if t.get("status") == "completed"]
        tool_calls_telemetry = [
            {
                "tool": t.get("tool", ""),
                "status": t.get("status", "unknown"),
                "duration_ms": int(t.get("duration_ms", 0) or 0),
                "risk_level": t.get("risk_level", "low"),
                "error": redact_secrets_in_text(str(t.get("error")), max_len=240) if t.get("error") else None,
            }
            for t in raw_tool_results
        ]

        # Derive honest browser activity telemetry (never fake idle if unused!)
        browser_tools = [
            t
            for t in raw_tool_results
            if str(t.get("tool", "")).startswith("playwright_") or t.get("tool") == "browser_search"
        ]
        visited_urls: list[str] = []
        blocked_requests: list[Any] = []
        screenshots: list[str] = []
        browser_status = "not_used"
        for bt in browser_tools:
            out = bt.get("output") or {}
            if bt.get("status") == "completed":
                for p in out.get("visited_pages", []) or []:
                    if p.get("final_url"):
                        visited_urls.append(str(p["final_url"]))
                    if p.get("screenshot_path"):
                        screenshots.append(str(p["screenshot_path"]))
                    blocked_requests.extend(p.get("blocked_requests", []) or [])
                if out.get("final_url"):
                    visited_urls.append(str(out["final_url"]))
                if out.get("screenshot_path"):
                    screenshots.append(str(out["screenshot_path"]))
                for cu in out.get("checked_urls", []) or []:
                    visited_urls.append(str(cu))
                if out.get("status") == "not_used" or out.get("verified_status") == "not_used":
                    browser_status = "not_used"
                elif visited_urls:
                    browser_status = "completed"
                elif out.get("blocked_requests"):
                    browser_status = "blocked"
            elif bt.get("status") in {"blocked_security", "denied"}:
                browser_status = "blocked"
            else:
                browser_status = "error"

        # Derive honest sandbox runtime telemetry from executed tools or tenant runtime record
        sandbox_info: dict[str, Any] = {
            "status": "not_used",
            "backend_mode": "none",
            "is_container_isolated": False,
        }
        for t in raw_tool_results:
            out = t.get("output") or {}
            meta = out.get("_sandbox_meta") or out.get("sandbox_meta")
            if isinstance(meta, dict):
                sandbox_info = {
                    "status": "executed",
                    **sanitize_structured_payload(meta, max_str_len=200),
                }
                break
        if sandbox_info["status"] == "not_used":
            active_rt = db.scalar(
                select(AgentSandboxRuntime)
                .where(AgentSandboxRuntime.tenant_id == tenant_uuid, AgentSandboxRuntime.status != "destroyed")
                .order_by(AgentSandboxRuntime.created_at.desc())
            )
            if active_rt is not None:
                sandbox_info = {
                    "status": active_rt.status,
                    "runtime_id": str(active_rt.id),
                    "agent_runtime_id": active_rt.agent_runtime_id,
                    "backend_mode": active_rt.backend_mode,
                    "is_container_isolated": active_rt.is_container_isolated,
                }

        baseline_tok = int(state.get("baseline_input_tokens") or 0)
        in_tok = int(state.get("input_tokens", 0))
        cached_tok = int(state.get("cached_tokens", 0))
        out_tok = int(state.get("output_tokens", 0))
        cost_usd = float(state.get("estimated_cost_usd", 0.0))
        opt_enabled = bool(state.get("enable_optimization", True))
        opt_methods = list(state.get("optimization_methods_used") or [])
        opt_telemetry = dict(state.get("optimization_telemetry") or {})
        intent_analysis = dict(state.get("intent_analysis") or {})
        guardrail_flags = list(state.get("guardrail_flags") or [])

        # Invalidate tenant response cache automatically after mutating workflow executions
        if any(t in {"sandbox_ocr_extract", "calendar_book_event", "onboarding_checklist_builder"} for t in tool_names):
            tenant_response_cache.invalidate_tenant(tenant_uuid)

        agent_slug = state.get("selected_agent_id") or state.get("routed_agent_id") or state.get("requested_agent_id", "unknown")
        exec_log = ExecutionLog(
            tenant_id=tenant_uuid,
            rental_id=rental_uuid,
            conversation_id=conv_uuid,
            user_id=actor_uuid,
            prompt_preview=redact_secrets_in_text((state.get("user_input") or "")[:300]),
            classifier_result=state.get("classifier_result", "in_domain"),
            status=state.get("execution_status", "completed"),
            latency_ms=total_latency_ms,
            model_tier_used=state.get("model_used") or state.get("model_tier_override") or "deterministic_tier_0",
            steps_json=list(state.get("trace_steps", [])),
            citations_json=list(state.get("citations", [])),
            browser_activity_json={
                "status": browser_status,
                "agent_slug": agent_slug,
                "requested_agent_slug": state.get("requested_agent_id", agent_slug),
                "tools": tool_names,
                "visited_urls": visited_urls[:10],
                "blocked_requests": blocked_requests[:10],
                "screenshots": screenshots[:5],
            },
            runtime_telemetry_json={
                "tool_calls": tool_calls_telemetry,
                "sandbox": sandbox_info,
                "intent_analysis": intent_analysis,
                "guardrail_flags": guardrail_flags,
                "optimization": opt_telemetry,
                "token_usage": {
                    "baseline_input_tokens": baseline_tok,
                    "input_tokens": in_tok,
                    "cached_tokens": cached_tok,
                    "output_tokens": out_tok,
                    "total_tokens": in_tok + out_tok,
                    "estimated_cost_usd": cost_usd,
                },
            },
        )
        db.add(exec_log)
        db.flush()
        exec_log_id = str(exec_log.id)

        if in_tok + cached_tok + out_tok > 0:
            db.add(
                TokenUsage(
                    tenant_id=tenant_uuid,
                    rental_id=rental_uuid,
                    execution_log_id=exec_log.id,
                    step_name=agent_slug,
                    model_id=state.get("model_used", "deterministic"),
                    baseline_input_tokens=baseline_tok,
                    input_tokens=in_tok,
                    cached_tokens=cached_tok,
                    output_tokens=out_tok,
                    duration_ms=total_latency_ms,
                    tool_calls_count=len(raw_tool_results),
                    optimization_enabled=opt_enabled,
                    optimization_methods_json=opt_methods,
                    estimated_cost_usd=cost_usd,
                )
            )

        db.add(
            AuditLog(
                tenant_id=tenant_uuid,
                actor_user_id=actor_uuid,
                rental_id=rental_uuid,
                action="agent.execute",
                resource_type="hr_workflow",
                resource_id=str(rental_uuid),
                status="blocked"
                if state.get("classifier_result") != "in_domain"
                else state.get("execution_status", "completed"),
                metadata_json={
                    "agent_slug": agent_slug,
                    "requested_agent_slug": state.get("requested_agent_id"),
                    "classifier_result": state.get("classifier_result"),
                    "tools": tool_names,
                    "provider": state.get("llm_provider_used", "deterministic"),
                },
            )
        )
        db.flush()

    return {
        "latency_ms": total_latency_ms,
        "execution_log_id": exec_log_id,
        "trace_step": {"status": "ok", "detail": f"telemetry recorded ({total_latency_ms}ms)"},
    }


def _route_after_tenant(state: AgentExecutionState) -> str:
    return "classify_intent" if state.get("permissions_ok") else "build_response"


def _route_after_intent(state: AgentExecutionState) -> str:
    if state.get("classifier_result") in {
        "invalid_input",
        "blocked_injection",
        "blocked_policy_fairness",
        "blocked_auto_reject",
        "needs_clarification",
    }:
        return "build_response"
    return "classify_domain"


def _route_after_domain(state: AgentExecutionState) -> str:
    return "check_permissions" if state.get("domain_allowed") else "build_response"


def _route_after_permissions(state: AgentExecutionState) -> str:
    return "validate_input" if state.get("permissions_ok") else "build_response"


def _route_after_input(state: AgentExecutionState) -> str:
    return "select_agent" if state.get("input_valid") else "build_response"


def build_agent_workflow():
    """Compile the shared multi-stage LangGraph workflow reused by all 7 HR capabilities."""
    graph = StateGraph(AgentExecutionState)

    graph.add_node("authenticate", node_authenticate)
    graph.add_node("validate_tenant", node_validate_tenant)
    graph.add_node("classify_intent", node_classify_intent)
    graph.add_node("classify_domain", node_classify_domain)
    graph.add_node("check_permissions", node_check_permissions)
    graph.add_node("validate_input", node_validate_input)
    graph.add_node("select_agent", node_select_agent)
    graph.add_node("execute_agent", node_execute_agent)
    graph.add_node("execute_tools", node_execute_tools)
    graph.add_node("validate_output", node_validate_output)
    graph.add_node("check_guardrails", node_check_guardrails)
    graph.add_node("build_response", node_build_response)
    graph.add_node("log_execution", node_log_execution)

    graph.add_edge(START, "authenticate")
    graph.add_edge("authenticate", "validate_tenant")
    graph.add_conditional_edges("validate_tenant", _route_after_tenant)
    graph.add_conditional_edges("classify_intent", _route_after_intent)
    graph.add_conditional_edges("classify_domain", _route_after_domain)
    graph.add_conditional_edges("check_permissions", _route_after_permissions)
    graph.add_conditional_edges("validate_input", _route_after_input)
    graph.add_edge("select_agent", "execute_agent")
    graph.add_edge("execute_agent", "execute_tools")
    graph.add_edge("execute_tools", "validate_output")
    graph.add_edge("validate_output", "check_guardrails")
    graph.add_edge("check_guardrails", "build_response")
    graph.add_edge("build_response", "log_execution")
    graph.add_edge("log_execution", END)

    return graph.compile()


COMPILED_HR_WORKFLOW = build_agent_workflow()


def run_agent_workflow(
    *,
    agent: BaseSpecializedAgent,
    toolbox: AgentToolBox,
    db: Session,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_role: str,
    user_input: str,
    rental_id: Optional[uuid.UUID] = None,
    conversation_id: Optional[uuid.UUID] = None,
    structured_input: Optional[dict[str, Any]] = None,
    attachments: Optional[list[str]] = None,
    conversation_history: Optional[list[dict[str, str]]] = None,
    model_provider_override: Optional[str] = None,
    persist_telemetry: bool = True,
    enable_optimization: Optional[bool] = None,
    available_agents: Optional[dict[str, BaseSpecializedAgent]] = None,
) -> AgentExecutionState:
    """Invoke the compiled LangGraph HR workflow cleanly with isolated tenant context."""
    settings = get_settings()
    opt_flag = settings.ENABLE_CONTEXT_OPTIMIZATION if enable_optimization is None else bool(enable_optimization)
    initial_state: AgentExecutionState = {
        "request_id": str(uuid.uuid4()),
        "user_input": user_input,
        "structured_input": structured_input or {},
        "attachments": attachments or [],
        "actor_user_id": str(actor_user_id),
        "actor_role": actor_role,
        "tenant_id": str(tenant_id),
        "rental_id": str(rental_id) if rental_id else None,
        "requested_agent_id": agent.agent_id,
        "routed_agent_id": agent.agent_id,
        "conversation_history": conversation_history or [],
        "model_provider_override": model_provider_override,
        "enable_optimization": opt_flag,
        "workflow_started_at_monotonic": time.perf_counter(),
        "guardrail_flags": [],
        "trace_steps": [],
        "tool_results": [],
    }
    monitor_run_id = monitor_tracker.start_run(
        tenant_id=tenant_id,
        workflow=agent.agent_id,
        prompt_preview=user_input,
        actor_user_id=actor_user_id,
    )
    config: RunnableConfig = {
        "recursion_limit": min(settings.MAX_WORKFLOW_STEPS_HARD_CAP, max(16, agent.execution_limits.max_steps + 4)),
        "configurable": {
            "agent": agent,
            "available_agents": available_agents or {agent.agent_id: agent},
            "toolbox": toolbox,
            "db": db,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "persist_telemetry": persist_telemetry,
            "started_at_ms": time.perf_counter() * 1000,
            "monitor_run_id": monitor_run_id,
        },
    }
    try:
        return COMPILED_HR_WORKFLOW.invoke(initial_state, config=config)
    finally:
        monitor_tracker.finish_run(monitor_run_id)
