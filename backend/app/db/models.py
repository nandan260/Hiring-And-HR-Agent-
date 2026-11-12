import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedMixin, TimestampMixin, utcnow


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    memberships: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(80), default="Technology", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)

    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrganizationMember(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_org_member_tenant_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Roles: platform_admin, business_owner, business_admin, business_employee
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="business_employee")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship(back_populates="memberships")
    organization: Mapped["Organization"] = relationship(back_populates="members")


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AgentCatalog(Base, TimestampMixin):
    __tablename__ = "agent_catalog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(80), default="hiring-hr", nullable=False, index=True)
    short_tagline: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    industries: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("4.90"), nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    base_monthly_price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_tier: Mapped[str] = mapped_column(String(30), default="growth", nullable=False)
    estimated_cost_per_run: Mapped[str] = mapped_column(String(60), default="$0.005 / run", nullable=False)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    browser_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    security_profile: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    token_efficiency: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    sample_in_domain_prompts: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    sample_out_of_domain_prompts: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    domain_keywords: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class AgentVersion(Base, TimestampMixin):
    __tablename__ = "agent_versions"
    __table_args__ = (UniqueConstraint("agent_id", "version", name="uq_agent_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_catalog.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    base_system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    supported_tasks: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    default_tool_slugs: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    default_model_tier: Mapped[str] = mapped_column(String(40), default="auto_cascade", nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    agent: Mapped["AgentCatalog"] = relationship(back_populates="versions")


class SubscriptionPlan(Base, TimestampMixin):
    __tablename__ = "subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    monthly_price_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    included_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    overage_per_million_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    max_concurrent_runs: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    features: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_demo_plan: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AgentRental(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "agent_rentals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_catalog.id"), nullable=False, index=True
    )
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id"), nullable=False
    )
    subscription_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(150), nullable=False)
    # Status: active, paused, cancelled
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False, index=True)
    rented_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    agent: Mapped["AgentCatalog"] = relationship()
    version: Mapped["AgentVersion"] = relationship()
    plan: Mapped["SubscriptionPlan"] = relationship()
    configuration: Mapped[Optional["AgentConfiguration"]] = relationship(
        back_populates="rental", uselist=False, cascade="all, delete-orphan"
    )


class AgentConfiguration(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "agent_configurations"
    __table_args__ = (UniqueConstraint("rental_id", name="uq_config_rental"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False
    )
    custom_persona_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    kb_version_hash: Mapped[str] = mapped_column(String(64), default="kb_v1_init", nullable=False)
    model_routing_tier: Mapped[str] = mapped_column(String(40), default="auto_cascade", nullable=False)
    monthly_token_quota: Mapped[int] = mapped_column(BigInteger, default=2000000, nullable=False)
    allowed_domains: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    blind_screening_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    strict_pii_masking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    require_hitl_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_steps: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    extra_settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    rental: Mapped["AgentRental"] = relationship(back_populates="configuration")


class AgentConversation(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "agent_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), default="HR Workspace Thread", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="active", nullable=False)
    summary_memory: Mapped[str] = mapped_column(Text, default="", nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False)  # user, assistant, system_guardrail
    content: Mapped[str] = mapped_column(Text, nullable=False)
    classifier_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    conversation: Mapped["AgentConversation"] = relationship(back_populates="messages")


class ToolRegistry(Base, TimestampMixin):
    __tablename__ = "tool_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    mcp_server_slug: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    requires_hitl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auth_scheme: Mapped[str] = mapped_column(String(30), default="none", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    schema_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class ToolPermission(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "tool_permissions"
    __table_args__ = (UniqueConstraint("rental_id", "tool_id", name="uq_tool_perm_rental_tool"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_registry.id", ondelete="CASCADE"), nullable=False
    )
    is_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    credential_status: Mapped[str] = mapped_column(String(30), default="not_configured", nullable=False)
    # Never plaintext! Stored encrypted via Fernet/AES envelope in security.py
    encrypted_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    masked_secret_ref: Mapped[str] = mapped_column(String(200), default="Not bound", nullable=False)

    tool: Mapped["ToolRegistry"] = relationship()


class KnowledgeDocument(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), default="handbook", nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), default="application/pdf", nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_rel_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    min_role_access: Mapped[str] = mapped_column(String(40), default="business_employee", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="indexed", nullable=False)


class ExecutionLog(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    prompt_preview: Mapped[str] = mapped_column(Text, nullable=False)
    classifier_result: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_tier_used: Mapped[str] = mapped_column(String(40), default="tier_0_rule", nullable=False)
    steps_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    citations_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    browser_activity_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    runtime_telemetry_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class TokenUsage(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "token_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_log_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("execution_logs.id", ondelete="SET NULL"), nullable=True
    )
    step_name: Mapped[str] = mapped_column(String(80), nullable=False)
    model_id: Mapped[str] = mapped_column(String(80), nullable=False)
    baseline_input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_calls_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    optimization_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    optimization_methods_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"), nullable=False)


class BillingRecord(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "billing_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_plans.id"), nullable=False
    )
    billing_period: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. 2026-11
    base_amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    token_overage_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    total_amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="demo_active", nullable=False)
    is_demo_subscription: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)


class AuditLog(Base, TenantScopedMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    rental_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(60), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class KnowledgeChunk(Base, TenantScopedMixin):
    """Chunked, embedded knowledge segments stored with pgvector for tenant-isolated RAG."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_doc_idx"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    min_role_access: Mapped[str] = mapped_column(String(40), default="member", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Candidate(Base, TenantScopedMixin, TimestampMixin):
    """Tenant-isolated candidate profile and semantic resume embedding."""

    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_role: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    years_experience: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)
    skills_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    education_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    experience_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    resume_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="SET NULL"), nullable=True
    )
    match_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="screened", nullable=False)
    screening_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384), nullable=True)


class HitlApproval(Base, TenantScopedMixin, TimestampMixin):
    """Human-in-the-loop approval gate for consequential HR agent actions."""

    __tablename__ = "hitl_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False, index=True)
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewRecord(Base, TenantScopedMixin, TimestampMixin):
    """Tracked interview schedule entry managed by the Interview Scheduling Agent."""

    __tablename__ = "interviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    candidate_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role_title: Mapped[str] = mapped_column(String(200), nullable=False)
    interview_stage: Mapped[str] = mapped_column(String(80), default="technical_round", nullable=False)
    interviewer_emails: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    meeting_link: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="proposed", nullable=False)
    invitation_draft: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class OnboardingWorkflow(Base, TenantScopedMixin, TimestampMixin):
    """Employee onboarding state tracking docs, checklist, IT provisioning, team allocation, and training."""

    __tablename__ = "onboarding_workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rental_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    employee_name: Mapped[str] = mapped_column(String(200), nullable=False)
    employee_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role_title: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[str] = mapped_column(String(120), default="Engineering", nullable=False)
    start_date: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    current_stage: Mapped[str] = mapped_column(String(60), default="document_collection", nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    documents_status_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    checklist_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    it_provisioning_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    team_allocation_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    training_plan_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)


class AgentSandboxRuntime(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "agent_sandbox_runtimes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_runtime_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    rental_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_rentals.id", ondelete="SET NULL"), nullable=True
    )
    backend_mode: Mapped[str] = mapped_column(String(40), default="development_fallback", nullable=False)
    is_container_isolated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="created", nullable=False)
    container_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    image_name: Mapped[str] = mapped_column(String(150), default="hireflow-hr-sandbox:latest", nullable=False)
    workspace_path: Mapped[str] = mapped_column(Text, nullable=False)
    cpu_limit: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    network_mode: Mapped[str] = mapped_column(String(40), default="none", nullable=False)
    last_health_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    execution_logs_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    last_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    destroyed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class McpServerRecord(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "mcp_server_records"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_mcp_server_tenant_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    transport: Mapped[str] = mapped_column(String(20), default="stdio", nullable=False)
    command_or_url: Mapped[str] = mapped_column(Text, nullable=False)
    args_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    env_keys_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(30), default="pending_approval", nullable=False)
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    connection_status: Mapped[str] = mapped_column(String(30), default="not_checked", nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discovered_tools_json: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tool_permissions_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class McpExecutionLog(Base, TenantScopedMixin, TimestampMixin):
    __tablename__ = "mcp_execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_server_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    response_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
