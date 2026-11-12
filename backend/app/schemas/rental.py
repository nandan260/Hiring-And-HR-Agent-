from datetime import datetime
from typing import Literal
import uuid
from pydantic import BaseModel, Field


class RentAgentRequest(BaseModel):
    agent_slug: str = Field(min_length=2, max_length=80)
    subscription_plan_slug: str = Field(default="growth", max_length=50)
    display_name: str | None = Field(default=None, max_length=150)
    custom_persona_prompt: str | None = None
    monthly_token_quota: int | None = Field(default=None, ge=100000, le=50000000)


class AgentConfigurationUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=150)
    custom_persona_prompt: str | None = None
    model_routing_tier: Literal["auto_cascade", "slm_first", "flash_balanced"] | None = None
    monthly_token_quota: int | None = Field(default=None, ge=100000, le=50000000)
    allowed_domains: list[str] | None = None
    blind_screening_mode: bool | None = None
    strict_pii_masking: bool | None = None
    require_hitl_approval: bool | None = None
    max_steps: int | None = Field(default=None, ge=2, le=30)


class AgentConfigurationResponse(BaseModel):
    id: uuid.UUID
    rental_id: uuid.UUID
    custom_persona_prompt: str
    config_hash: str
    kb_version_hash: str
    model_routing_tier: str
    monthly_token_quota: int
    allowed_domains: list[str]
    blind_screening_mode: bool
    strict_pii_masking: bool
    require_hitl_approval: bool
    max_steps: int


class ToolPermissionResponse(BaseModel):
    id: uuid.UUID
    tool_id: uuid.UUID
    tool_slug: str
    tool_name: str
    mcp_server_slug: str | None
    execution_mode: str
    requires_hitl: bool
    is_allowed: bool
    credential_status: str
    masked_secret_ref: str


class ToolPermissionUpdateRequest(BaseModel):
    is_allowed: bool


class ToolCredentialBindRequest(BaseModel):
    api_key_or_token: str = Field(min_length=4, max_length=2048)


class KnowledgeDocumentResponse(BaseModel):
    id: uuid.UUID
    rental_id: uuid.UUID
    title: str
    original_filename: str
    source_type: str
    mime_type: str
    file_size_bytes: int
    sha256_checksum: str
    chunk_count: int
    min_role_access: str
    status: str
    created_at: datetime


class RentalResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: uuid.UUID
    agent_slug: str
    agent_name: str
    version: str
    subscription_plan_slug: str
    subscription_plan_name: str
    display_name: str
    status: str
    activated_at: datetime | None
    paused_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    tokens_used_this_month: int = 0
    tokens_saved_by_cache: int = 0
    configuration: AgentConfigurationResponse
    tool_permissions: list[ToolPermissionResponse]
    knowledge_documents: list[KnowledgeDocumentResponse]
