from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.models import AgentCatalog, AgentVersion, SubscriptionPlan, ToolRegistry
from ...db.session import get_db
from ...schemas.marketplace import (
    AgentCatalogSummaryResponse,
    AgentDetailResponse,
    CategorySummaryResponse,
    SubscriptionPlanResponse,
    ToolRegistryResponse,
)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

MARKETPLACE_CATEGORIES = [
    ("hiring-hr", "Hiring and HR", "Specialized AI agents for recruitment, onboarding, scheduling, policy desk, and people analytics.", "active"),
    ("business-finance", "Business and Finance", "Financial close, AP/AR reconciliation, and FP&A forecasting assistants.", "coming_soon"),
    ("healthcare", "Healthcare", "Clinical intake triage and HIPAA-isolated care coordination workflows.", "coming_soon"),
    ("customer-support-sales", "Customer Support and Sales", "Omnichannel CRM qualification and ticket deflection agents.", "coming_soon"),
    ("legal-compliance", "Legal and Compliance", "Contract redlining, DPA audit, and regulatory tracker assistants.", "coming_soon"),
    ("education", "Education", "Curriculum personalization and academic advising workflows.", "coming_soon"),
    ("operations-internal", "Operations and Internal Work", "IT helpdesk, vendor procurement, and internal SOP automation.", "coming_soon"),
]


def _get_latest_version(db: Session, agent_id) -> AgentVersion | None:
    return db.scalars(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent_id)
        .order_by(AgentVersion.is_latest.desc(), AgentVersion.created_at.desc())
    ).first()


@router.get("/categories", response_model=list[CategorySummaryResponse])
def list_categories(db: Session = Depends(get_db)) -> list[CategorySummaryResponse]:
    hr_count = len(
        db.scalars(
            select(AgentCatalog.id).where(AgentCatalog.category == "hiring-hr", AgentCatalog.is_active.is_(True))
        ).all()
    )
    return [
        CategorySummaryResponse(
            slug=slug,
            name=name,
            description=desc,
            status=cat_status,
            agent_count=hr_count if slug == "hiring-hr" else 0,
        )
        for slug, name, desc, cat_status in MARKETPLACE_CATEGORIES
    ]


@router.get("/plans", response_model=list[SubscriptionPlanResponse])
def list_subscription_plans(db: Session = Depends(get_db)) -> list[SubscriptionPlanResponse]:
    plans = db.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.monthly_price_usd.asc())).all()
    return [
        SubscriptionPlanResponse(
            id=p.id,
            slug=p.slug,
            name=p.name,
            monthly_price_usd=p.monthly_price_usd,
            included_tokens=p.included_tokens,
            overage_per_million_usd=p.overage_per_million_usd,
            max_concurrent_runs=p.max_concurrent_runs,
            features=list(p.features or []),
            is_demo_plan=p.is_demo_plan,
        )
        for p in plans
    ]


@router.get("/tools", response_model=list[ToolRegistryResponse])
def list_tool_registry(db: Session = Depends(get_db)) -> list[ToolRegistryResponse]:
    tools = db.scalars(select(ToolRegistry).order_by(ToolRegistry.category.asc(), ToolRegistry.slug.asc())).all()
    return [
        ToolRegistryResponse(
            id=t.id,
            slug=t.slug,
            name=t.name,
            mcp_server_slug=t.mcp_server_slug,
            category=t.category,
            execution_mode=t.execution_mode,
            requires_hitl=t.requires_hitl,
            auth_scheme=t.auth_scheme,
            description=t.description,
        )
        for t in tools
    ]


@router.get("/agents", response_model=list[AgentCatalogSummaryResponse])
def list_marketplace_agents(
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    industry: str | None = Query(default=None),
    price_tier: str | None = Query(default=None),
    max_price: Decimal | None = Query(default=None),
    min_rating: Decimal | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[AgentCatalogSummaryResponse]:
    stmt = select(AgentCatalog).where(AgentCatalog.is_active.is_(True)).order_by(AgentCatalog.featured.desc(), AgentCatalog.name.asc())
    if category:
        stmt = stmt.where(AgentCatalog.category == category)
    if price_tier:
        stmt = stmt.where(AgentCatalog.price_tier == price_tier)
    if max_price is not None:
        stmt = stmt.where(AgentCatalog.base_monthly_price_usd <= max_price)
    if min_rating is not None:
        stmt = stmt.where(AgentCatalog.rating >= min_rating)

    agents = db.scalars(stmt).all()
    q = (search or "").strip().lower()
    ind = (industry or "").strip().lower()

    results: list[AgentCatalogSummaryResponse] = []
    for agent in agents:
        if q:
            haystack = f"{agent.name} {agent.short_tagline} {agent.description} {' '.join(agent.domain_keywords or [])}".lower()
            if q not in haystack:
                continue
        if ind:
            if not any(i.lower() == ind for i in (agent.industries or [])):
                continue
        ver = _get_latest_version(db, agent.id)
        results.append(
            AgentCatalogSummaryResponse(
                id=agent.id,
                slug=agent.slug,
                name=agent.name,
                category=agent.category,
                short_tagline=agent.short_tagline,
                description=agent.description,
                industries=list(agent.industries or []),
                rating=agent.rating,
                review_count=agent.review_count,
                base_monthly_price_usd=agent.base_monthly_price_usd,
                price_tier=agent.price_tier,
                estimated_cost_per_run=agent.estimated_cost_per_run,
                featured=agent.featured,
                browser_enabled=agent.browser_enabled,
                latest_version=ver.version if ver else "1.0.0",
            )
        )
    return results


@router.get("/agents/{slug}", response_model=AgentDetailResponse)
def get_marketplace_agent_details(slug: str, db: Session = Depends(get_db)) -> AgentDetailResponse:
    agent = db.scalars(select(AgentCatalog).where(AgentCatalog.slug == slug, AgentCatalog.is_active.is_(True))).first()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent catalog entry not found")

    ver = _get_latest_version(db, agent.id)
    if ver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent version metadata missing")

    tool_slugs = list(ver.default_tool_slugs or [])
    tools = (
        db.scalars(select(ToolRegistry).where(ToolRegistry.slug.in_(tool_slugs))).all() if tool_slugs else []
    )
    tool_map = {t.slug: t for t in tools}
    ordered_tools = [tool_map[s] for s in tool_slugs if s in tool_map]

    return AgentDetailResponse(
        id=agent.id,
        slug=agent.slug,
        name=agent.name,
        category=agent.category,
        short_tagline=agent.short_tagline,
        description=agent.description,
        industries=list(agent.industries or []),
        rating=agent.rating,
        review_count=agent.review_count,
        base_monthly_price_usd=agent.base_monthly_price_usd,
        price_tier=agent.price_tier,
        estimated_cost_per_run=agent.estimated_cost_per_run,
        featured=agent.featured,
        browser_enabled=agent.browser_enabled,
        latest_version=ver.version,
        browser_notes=agent.browser_notes,
        security_profile=dict(agent.security_profile or {}),
        token_efficiency=dict(agent.token_efficiency or {}),
        sample_in_domain_prompts=list(agent.sample_in_domain_prompts or []),
        sample_out_of_domain_prompts=list(agent.sample_out_of_domain_prompts or []),
        domain_keywords=list(agent.domain_keywords or []),
        base_system_prompt=ver.base_system_prompt,
        capabilities=list(ver.capabilities or []),
        supported_tasks=list(ver.supported_tasks or []),
        default_model_tier=ver.default_model_tier,
        tools=[
            ToolRegistryResponse(
                id=t.id,
                slug=t.slug,
                name=t.name,
                mcp_server_slug=t.mcp_server_slug,
                category=t.category,
                execution_mode=t.execution_mode,
                requires_hitl=t.requires_hitl,
                auth_scheme=t.auth_scheme,
                description=t.description,
            )
            for t in ordered_tools
        ],
    )
