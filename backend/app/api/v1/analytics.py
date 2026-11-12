from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...core.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_tenant_db,
    require_roles,
)
from ...db.models import (
    AgentRental,
    AuditLog,
    BillingRecord,
    ExecutionLog,
    TokenUsage,
)
from ...schemas.telemetry import (
    AuditLogResponse,
    BillingRecordResponse,
    ExecutionLogResponse,
    TokenUsageItemResponse,
    UsageSummaryResponse,
)

router = APIRouter(tags=["Analytics & Logs"])


@router.get("/usage/summary", response_model=UsageSummaryResponse)
def get_usage_summary(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> UsageSummaryResponse:
    rentals = db.scalars(
        select(AgentRental).where(AgentRental.tenant_id == principal.tenant_id)
    ).all()
    active_count = sum(1 for r in rentals if r.status == "active")
    paused_count = sum(1 for r in rentals if r.status == "paused")
    cancelled_count = sum(1 for r in rentals if r.status == "cancelled")

    total_execs = db.scalar(
        select(func.count(ExecutionLog.id)).where(ExecutionLog.tenant_id == principal.tenant_id)
    ) or 0
    rejected_execs = db.scalar(
        select(func.count(ExecutionLog.id)).where(
            ExecutionLog.tenant_id == principal.tenant_id,
            ExecutionLog.status.in_(["rejected", "blocked"]),
        )
    ) or 0

    tok = db.execute(
        select(
            func.coalesce(func.sum(TokenUsage.input_tokens), 0),
            func.coalesce(func.sum(TokenUsage.cached_tokens), 0),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0),
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), Decimal("0")),
        ).where(TokenUsage.tenant_id == principal.tenant_id)
    ).one()

    return UsageSummaryResponse(
        tenant_id=principal.tenant_id,
        active_rentals=active_count,
        paused_rentals=paused_count,
        cancelled_rentals=cancelled_count,
        total_executions=int(total_execs),
        rejected_executions=int(rejected_execs),
        total_input_tokens=int(tok[0] or 0),
        total_cached_tokens=int(tok[1] or 0),
        total_output_tokens=int(tok[2] or 0),
        estimated_cost_usd=Decimal(tok[3] or 0),
    )


@router.get("/usage/tokens", response_model=list[TokenUsageItemResponse])
def list_token_usage(
    rental_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[TokenUsageItemResponse]:
    stmt = (
        select(TokenUsage)
        .where(TokenUsage.tenant_id == principal.tenant_id)
        .order_by(TokenUsage.created_at.desc())
        .limit(limit)
    )
    if rental_id is not None:
        stmt = stmt.where(TokenUsage.rental_id == rental_id)

    rows = db.scalars(stmt).all()
    return [
        TokenUsageItemResponse(
            id=r.id,
            rental_id=r.rental_id,
            execution_log_id=r.execution_log_id,
            step_name=r.step_name,
            model_id=r.model_id,
            input_tokens=r.input_tokens,
            cached_tokens=r.cached_tokens,
            output_tokens=r.output_tokens,
            estimated_cost_usd=r.estimated_cost_usd,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/billing/records", response_model=list[BillingRecordResponse])
def list_billing_records(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[BillingRecordResponse]:
    rows = db.scalars(
        select(BillingRecord)
        .where(BillingRecord.tenant_id == principal.tenant_id)
        .order_by(BillingRecord.created_at.desc())
    ).all()
    return [
        BillingRecordResponse(
            id=b.id,
            tenant_id=b.tenant_id,
            rental_id=b.rental_id,
            subscription_plan_id=b.subscription_plan_id,
            billing_period=b.billing_period,
            base_amount_usd=b.base_amount_usd,
            token_overage_usd=b.token_overage_usd,
            total_amount_usd=b.total_amount_usd,
            status=b.status,
            is_demo_subscription=b.is_demo_subscription,
            description=b.description,
            created_at=b.created_at,
        )
        for b in rows
    ]


@router.get("/execution-logs", response_model=list[ExecutionLogResponse])
def list_execution_logs(
    rental_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_tenant_db),
) -> list[ExecutionLogResponse]:
    stmt = (
        select(ExecutionLog)
        .where(ExecutionLog.tenant_id == principal.tenant_id)
        .order_by(ExecutionLog.created_at.desc())
        .limit(limit)
    )
    if rental_id is not None:
        stmt = stmt.where(ExecutionLog.rental_id == rental_id)

    rows = db.scalars(stmt).all()
    return [
        ExecutionLogResponse(
            id=e.id,
            tenant_id=e.tenant_id,
            rental_id=e.rental_id,
            conversation_id=e.conversation_id,
            prompt_preview=e.prompt_preview,
            classifier_result=e.classifier_result,
            status=e.status,
            latency_ms=e.latency_ms,
            model_tier_used=e.model_tier_used,
            steps_json=list(e.steps_json or []),
            citations_json=list(e.citations_json or []),
            browser_activity_json=dict(e.browser_activity_json or {}),
            created_at=e.created_at,
        )
        for e in rows
    ]


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    principal: AuthenticatedPrincipal = Depends(require_roles("business_owner", "business_admin", "platform_admin")),
    db: Session = Depends(get_tenant_db),
) -> list[AuditLogResponse]:
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.tenant_id == principal.tenant_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    ).all()
    return [
        AuditLogResponse(
            id=a.id,
            tenant_id=a.tenant_id,
            actor_user_id=a.actor_user_id,
            rental_id=a.rental_id,
            action=a.action,
            resource_type=a.resource_type,
            resource_id=a.resource_id,
            status=a.status,
            ip_address=a.ip_address,
            metadata_json=dict(a.metadata_json or {}),
            created_at=a.created_at,
        )
        for a in rows
    ]
