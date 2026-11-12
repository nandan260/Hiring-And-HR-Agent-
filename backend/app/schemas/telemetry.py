from datetime import datetime
from decimal import Decimal
import uuid
from pydantic import BaseModel


class ExecutionLogResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    rental_id: uuid.UUID
    conversation_id: uuid.UUID | None
    prompt_preview: str
    classifier_result: str
    status: str
    latency_ms: int
    model_tier_used: str
    steps_json: list[dict]
    citations_json: list[str]
    browser_activity_json: dict
    created_at: datetime


class TokenUsageItemResponse(BaseModel):
    id: uuid.UUID
    rental_id: uuid.UUID
    execution_log_id: uuid.UUID | None
    step_name: str
    model_id: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    created_at: datetime


class UsageSummaryResponse(BaseModel):
    tenant_id: uuid.UUID
    active_rentals: int
    paused_rentals: int
    cancelled_rentals: int
    total_executions: int
    rejected_executions: int
    total_input_tokens: int
    total_cached_tokens: int
    total_output_tokens: int
    estimated_cost_usd: Decimal


class BillingRecordResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    rental_id: uuid.UUID
    subscription_plan_id: uuid.UUID
    billing_period: str
    base_amount_usd: Decimal
    token_overage_usd: Decimal
    total_amount_usd: Decimal
    status: str
    is_demo_subscription: bool
    description: str
    created_at: datetime


class AuditLogResponse(BaseModel):
    id: int
    tenant_id: uuid.UUID
    actor_user_id: uuid.UUID | None
    rental_id: uuid.UUID | None
    action: str
    resource_type: str
    resource_id: str
    status: str
    ip_address: str | None
    metadata_json: dict
    created_at: datetime
