"""Initial multi-tenant schema with PostgreSQL Row-Level Security

Revision ID: 20261111_0001
Revises:
Create Date: 2026-11-11 10:15:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261111_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_SCOPED_TABLES = [
    "organization_members",
    "agent_rentals",
    "agent_configurations",
    "agent_conversations",
    "messages",
    "tool_permissions",
    "knowledge_documents",
    "execution_logs",
    "token_usage",
    "billing_records",
    "audit_logs",
]


def upgrade() -> None:
    # 1. Global / Control-Plane Tables
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("industry", sa.String(80), nullable=False, server_default="Technology"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "revoked_tokens",
        sa.Column("jti", sa.String(64), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_revoked_tokens_user_id", "revoked_tokens", ["user_id"])

    op.create_table(
        "agent_catalog",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.String(80), nullable=False, server_default="hiring-hr"),
        sa.Column("short_tagline", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("industries", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rating", sa.Numeric(3, 2), nullable=False, server_default="4.90"),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("base_monthly_price_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("price_tier", sa.String(30), nullable=False, server_default="growth"),
        sa.Column("estimated_cost_per_run", sa.String(60), nullable=False, server_default="$0.005 / run"),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("browser_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("browser_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("security_profile", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("token_efficiency", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sample_in_domain_prompts", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sample_out_of_domain_prompts", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("domain_keywords", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_catalog_slug", "agent_catalog", ["slug"], unique=True)
    op.create_index("ix_agent_catalog_category", "agent_catalog", ["category"])

    op.create_table(
        "agent_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_catalog.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("base_system_prompt", sa.Text(), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("supported_tasks", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("default_tool_slugs", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("default_model_tier", sa.String(40), nullable=False, server_default="auto_cascade"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_version"),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])

    op.create_table(
        "subscription_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("monthly_price_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("included_tokens", sa.BigInteger(), nullable=False),
        sa.Column("overage_per_million_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_concurrent_runs", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("features", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_demo_plan", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "tool_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("mcp_server_slug", sa.String(80), nullable=True),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("execution_mode", sa.String(40), nullable=False),
        sa.Column("requires_hitl", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("auth_scheme", sa.String(30), nullable=False, server_default="none"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("schema_summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_tool_registry_slug", "tool_registry", ["slug"], unique=True)

    # 2. Tenant-Scoped Tables (Mandatory tenant_id + PostgreSQL RLS)
    op.create_table(
        "organization_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(40), nullable=False, server_default="business_employee"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_org_member_tenant_user"),
    )
    op.create_index("ix_organization_members_tenant_id", "organization_members", ["tenant_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    op.create_table(
        "agent_rentals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_catalog.id"), nullable=False),
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_versions.id"), nullable=False),
        sa.Column("subscription_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id"), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("rented_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_rentals_tenant_id", "agent_rentals", ["tenant_id"])
    op.create_index("ix_agent_rentals_status", "agent_rentals", ["status"])

    op.create_table(
        "agent_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rental_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("custom_persona_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("kb_version_hash", sa.String(64), nullable=False, server_default="kb_v1_init"),
        sa.Column("model_routing_tier", sa.String(40), nullable=False, server_default="auto_cascade"),
        sa.Column("monthly_token_quota", sa.BigInteger(), nullable=False, server_default="2000000"),
        sa.Column("allowed_domains", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("blind_screening_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("strict_pii_masking", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("require_hitl_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("extra_settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("rental_id", name="uq_config_rental"),
    )
    op.create_index("ix_agent_configurations_tenant_id", "agent_configurations", ["tenant_id"])

    op.create_table(
        "agent_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rental_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False, server_default="HR Workspace Thread"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("summary_memory", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_conversations_tenant_id", "agent_conversations", ["tenant_id"])
    op.create_index("ix_agent_conversations_rental_id", "agent_conversations", ["rental_id"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("classifier_result", sa.String(50), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "tool_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rental_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tool_registry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("credential_status", sa.String(30), nullable=False, server_default="not_configured"),
        sa.Column("encrypted_secret", sa.Text(), nullable=True),
        sa.Column("masked_secret_ref", sa.String(200), nullable=False, server_default="Not bound"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("rental_id", "tool_id", name="uq_tool_perm_rental_tool"),
    )
    op.create_index("ix_tool_permissions_tenant_id", "tool_permissions", ["tenant_id"])
    op.create_index("ix_tool_permissions_rental_id", "tool_permissions", ["rental_id"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rental_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="handbook"),
        sa.Column("mime_type", sa.String(120), nullable=False, server_default="application/pdf"),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("storage_rel_path", sa.Text(), nullable=False),
        sa.Column("sha256_checksum", sa.String(64), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_role_access", sa.String(40), nullable=False, server_default="business_employee"),
        sa.Column("status", sa.String(30), nullable=False, server_default="indexed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_knowledge_documents_tenant_id", "knowledge_documents", ["tenant_id"])
    op.create_index("ix_knowledge_documents_rental_id", "knowledge_documents", ["rental_id"])

    op.create_table(
        "execution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rental_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("prompt_preview", sa.Text(), nullable=False),
        sa.Column("classifier_result", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model_tier_used", sa.String(40), nullable=False, server_default="tier_0_rule"),
        sa.Column("steps_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("citations_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("browser_activity_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_execution_logs_tenant_id", "execution_logs", ["tenant_id"])
    op.create_index("ix_execution_logs_rental_id", "execution_logs", ["rental_id"])

    op.create_table(
        "token_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rental_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_log_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("execution_logs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("step_name", sa.String(80), nullable=False),
        sa.Column("model_id", sa.String(80), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_token_usage_tenant_id", "token_usage", ["tenant_id"])
    op.create_index("ix_token_usage_rental_id", "token_usage", ["rental_id"])

    op.create_table(
        "billing_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rental_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("subscription_plans.id"), nullable=False),
        sa.Column("billing_period", sa.String(20), nullable=False),
        sa.Column("base_amount_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("token_overage_usd", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("total_amount_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="demo_active"),
        sa.Column("is_demo_subscription", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_billing_records_tenant_id", "billing_records", ["tenant_id"])
    op.create_index("ix_billing_records_rental_id", "billing_records", ["rental_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rental_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(60), nullable=False),
        sa.Column("resource_id", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="success"),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_rental_id", "audit_logs", ["rental_id"])

    # 3. Non-superuser PostgreSQL runtime role + FORCE Row-Level Security
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rent_agent_app') THEN
                CREATE ROLE rent_agent_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO rent_agent_app;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rent_agent_app;")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rent_agent_app;")
    # Append-only immutability on audit_logs for runtime role
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM rent_agent_app;")

    for table in TENANT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
                USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
                WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid);
            """
        )


def downgrade() -> None:
    for table in reversed(TENANT_SCOPED_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
        op.drop_table(table)

    op.drop_table("tool_registry")
    op.drop_table("subscription_plans")
    op.drop_table("agent_versions")
    op.drop_table("agent_catalog")
    op.drop_table("revoked_tokens")
    op.drop_table("organizations")
    op.drop_table("users")
