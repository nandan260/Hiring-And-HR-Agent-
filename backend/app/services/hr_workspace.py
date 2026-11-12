"""Workspace provisioning and helpers for the unified HireFlow AI Hiring & HR Agent."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents.framework.classifier import HR_WORKFLOW_DISPLAY_NAMES
from app.db.models import (
    AgentCatalog,
    AgentConfiguration,
    AgentRental,
    AgentVersion,
    SubscriptionPlan,
    TokenUsage,
    ToolPermission,
    ToolRegistry,
)

HR_WORKFLOW_SLUGS: tuple[str, ...] = (
    "recruitment-screening",
    "jd-generator",
    "candidate-shortlisting",
    "interview-scheduling",
    "employee-onboarding",
    "hr-policy-support",
    "hr-analytics",
)


def _compute_config_hash(rental_id: uuid.UUID, persona: str, model_tier: str, blind: bool) -> str:
    raw = f"{rental_id}:{persona}:{model_tier}:{blind}".encode("utf-8")
    return "cfg_" + hashlib.sha256(raw).hexdigest()[:12]


def ensure_tenant_hr_workflows(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, AgentRental]:
    """
    Idempotently ensure all 7 specialized HR workflows exist as active workspace configurations
    for the authenticated tenant, without requiring any marketplace checkout step.
    """
    existing_rows = db.execute(
        select(AgentRental, AgentCatalog)
        .join(AgentCatalog, AgentCatalog.id == AgentRental.agent_id)
        .where(
            AgentRental.tenant_id == tenant_id,
            AgentCatalog.slug.in_(HR_WORKFLOW_SLUGS),
        )
        .order_by(AgentRental.created_at.desc())
    ).all()

    by_slug: dict[str, AgentRental] = {}
    for rental, catalog in existing_rows:
        if catalog.slug not in by_slug:
            by_slug[catalog.slug] = rental
        elif by_slug[catalog.slug].status != "active" and rental.status == "active":
            by_slug[catalog.slug] = rental

    missing = [slug for slug in HR_WORKFLOW_SLUGS if slug not in by_slug]
    if not missing:
        return by_slug

    default_plan = (
        db.scalars(
            select(SubscriptionPlan).where(SubscriptionPlan.slug.in_(["enterprise", "growth", "starter"]))
        ).first()
        or db.scalars(select(SubscriptionPlan)).first()
    )
    if default_plan is None:
        return by_slug

    # Inherit workspace quota / guardrail preferences if tenant already configured at least one workflow
    existing_cfg = db.scalars(
        select(AgentConfiguration)
        .where(AgentConfiguration.tenant_id == tenant_id)
        .order_by(AgentConfiguration.created_at.asc())
    ).first()
    base_quota = existing_cfg.monthly_token_quota if existing_cfg else default_plan.included_tokens
    base_tier = existing_cfg.model_routing_tier if existing_cfg else "auto_cascade"
    base_extra = dict(existing_cfg.extra_settings or {}) if existing_cfg else {}

    now = datetime.now(timezone.utc)
    for slug in missing:
        catalog = db.scalars(select(AgentCatalog).where(AgentCatalog.slug == slug)).first()
        if catalog is None:
            continue
        version = db.scalars(
            select(AgentVersion)
            .where(AgentVersion.agent_id == catalog.id)
            .order_by(AgentVersion.is_latest.desc(), AgentVersion.created_at.desc())
        ).first()
        if version is None:
            continue

        wf_name = HR_WORKFLOW_DISPLAY_NAMES.get(slug, catalog.name)
        rental = AgentRental(
            tenant_id=tenant_id,
            agent_id=catalog.id,
            agent_version_id=version.id,
            subscription_plan_id=default_plan.id,
            display_name=f"{wf_name} Workflow"[:150],
            status="active",
            rented_by_user_id=actor_user_id,
            activated_at=now,
        )
        db.add(rental)
        db.flush()

        cfg = AgentConfiguration(
            tenant_id=tenant_id,
            rental_id=rental.id,
            custom_persona_prompt=existing_cfg.custom_persona_prompt if existing_cfg else "",
            config_hash=_compute_config_hash(rental.id, "", base_tier, slug == "recruitment-screening"),
            kb_version_hash="kb_v1_workspace",
            model_routing_tier=base_tier or version.default_model_tier,
            monthly_token_quota=base_quota,
            allowed_domains=[],
            blind_screening_mode=existing_cfg.blind_screening_mode if existing_cfg else (slug == "recruitment-screening"),
            strict_pii_masking=existing_cfg.strict_pii_masking if existing_cfg else True,
            require_hitl_approval=existing_cfg.require_hitl_approval if existing_cfg else True,
            max_steps=12,
            extra_settings=base_extra,
        )
        db.add(cfg)

        tool_slugs = list(version.default_tool_slugs or [])
        tools = db.scalars(select(ToolRegistry).where(ToolRegistry.slug.in_(tool_slugs))).all() if tool_slugs else []
        for tool in tools:
            db.add(
                ToolPermission(
                    tenant_id=tenant_id,
                    rental_id=rental.id,
                    tool_id=tool.id,
                    is_allowed=True,
                    credential_status="not_configured",
                    encrypted_secret=None,
                    masked_secret_ref="Not bound" if tool.auth_scheme != "none" else "No secret required",
                )
            )
        by_slug[slug] = rental

    db.flush()
    return by_slug


def get_monthly_token_usage(db: Session, *, tenant_id: uuid.UUID) -> int:
    now_utc = datetime.now(timezone.utc)
    month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = db.scalar(
        select(func.coalesce(func.sum(TokenUsage.input_tokens + TokenUsage.output_tokens), 0)).where(
            TokenUsage.tenant_id == tenant_id,
            TokenUsage.created_at >= month_start,
        )
    )
    return int(used or 0)
