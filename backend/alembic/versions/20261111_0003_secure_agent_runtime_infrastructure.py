"""Secure agent runtime infrastructure tables and telemetry

Revision ID: 20261111_0003
Revises: 20261111_0002
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261111_0003"
down_revision: Union[str, None] = "20261111_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TENANT_SCOPED_TABLES = [
    "agent_sandbox_runtimes",
    "mcp_server_records",
    "mcp_execution_logs",
]


def upgrade() -> None:
    op.add_column(
        "execution_logs",
        sa.Column(
            "runtime_telemetry_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.create_table(
        "agent_sandbox_runtimes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_runtime_id", sa.String(80), nullable=False, unique=True),
        sa.Column(
            "rental_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_rentals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("backend_mode", sa.String(40), nullable=False, server_default="development_fallback"),
        sa.Column("is_container_isolated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(30), nullable=False, server_default="created"),
        sa.Column("container_id", sa.String(128), nullable=True),
        sa.Column("image_name", sa.String(150), nullable=False, server_default="hireflow-hr-sandbox:latest"),
        sa.Column("workspace_path", sa.Text(), nullable=False),
        sa.Column("cpu_limit", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("memory_limit_mb", sa.Integer(), nullable=False, server_default="512"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("network_mode", sa.String(40), nullable=False, server_default="none"),
        sa.Column("last_health_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("execution_logs_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("last_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("destroyed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_sandbox_runtimes_tenant_id", "agent_sandbox_runtimes", ["tenant_id"])
    op.create_index(
        "ix_agent_sandbox_runtimes_agent_runtime_id",
        "agent_sandbox_runtimes",
        ["agent_runtime_id"],
        unique=True,
    )

    op.create_table(
        "mcp_server_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("transport", sa.String(20), nullable=False, server_default="stdio"),
        sa.Column("command_or_url", sa.Text(), nullable=False),
        sa.Column("args_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("env_keys_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approval_status", sa.String(30), nullable=False, server_default="pending_approval"),
        sa.Column(
            "approved_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connection_status", sa.String(30), nullable=False, server_default="not_checked"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("discovered_tools_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tool_permissions_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_mcp_server_tenant_slug"),
    )
    op.create_index("ix_mcp_server_records_tenant_id", "mcp_server_records", ["tenant_id"])

    op.create_table(
        "mcp_execution_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "server_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mcp_server_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tool_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_summary_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response_summary_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_mcp_execution_logs_tenant_id", "mcp_execution_logs", ["tenant_id"])
    op.create_index("ix_mcp_execution_logs_server_id", "mcp_execution_logs", ["server_id"])

    for table in NEW_TENANT_SCOPED_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rent_agent_app;")
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
    for table in reversed(NEW_TENANT_SCOPED_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")
        op.drop_table(table)
    op.drop_column("execution_logs", "runtime_telemetry_json")
