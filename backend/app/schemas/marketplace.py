from decimal import Decimal
import uuid
from pydantic import BaseModel


class CategorySummaryResponse(BaseModel):
    slug: str
    name: str
    description: str
    status: str
    agent_count: int


class ToolRegistryResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    mcp_server_slug: str | None
    category: str
    execution_mode: str
    requires_hitl: bool
    auth_scheme: str
    description: str


class SubscriptionPlanResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    monthly_price_usd: Decimal
    included_tokens: int
    overage_per_million_usd: Decimal
    max_concurrent_runs: int
    features: list[str]
    is_demo_plan: bool


class AgentCatalogSummaryResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    category: str
    short_tagline: str
    description: str
    industries: list[str]
    rating: Decimal
    review_count: int
    base_monthly_price_usd: Decimal
    price_tier: str
    estimated_cost_per_run: str
    featured: bool
    browser_enabled: bool
    latest_version: str


class AgentDetailResponse(AgentCatalogSummaryResponse):
    browser_notes: str
    security_profile: dict
    token_efficiency: dict
    sample_in_domain_prompts: list[str]
    sample_out_of_domain_prompts: list[str]
    domain_keywords: list[str]
    base_system_prompt: str
    capabilities: list[str]
    supported_tasks: list[str]
    default_model_tier: str
    tools: list[ToolRegistryResponse]
