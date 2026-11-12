"""Enable pgvector and add tenant-scoped HR agent tables

Revision ID: 20261111_0002
Revises: 20261111_0001
Create Date: 2026-11-11 10:42:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20261111_0002"
down_revision: Union[str, Sequence[str], None] = "20261111_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TENANT_SCOPED_TABLES = [
    "knowledge_chunks",
    "candidates",
    "hitl_approvals",
    "interviews",
    "onboarding_workflows",
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rental_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_title", sa.String(255), nullable=True),
        sa.Column("min_role_access", sa.String(40), nullable=False, server_default="member"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_knowledge_chunk_doc_idx"),
    )
    op.create_index("ix_knowledge_chunks_tenant_id", "knowledge_chunks", ["tenant_id"])
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_rental_id", "knowledge_chunks", ["rental_id"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);"
    )

    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rental_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_rentals.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("target_role", sa.String(200), nullable=False),
        sa.Column("years_experience", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("skills_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("education_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("experience_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("resume_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("match_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="screened"),
        sa.Column(
            "screening_summary_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("embedding", Vector(384), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_candidates_tenant_id", "candidates", ["tenant_id"])
    op.create_index("ix_candidates_rental_id", "candidates", ["rental_id"])
    op.create_index("ix_candidates_target_role", "candidates", ["target_role"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_candidates_embedding "
        "ON candidates USING hnsw (embedding vector_cosine_ops);"
    )

    op.create_table(
        "hitl_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rental_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("agent_slug", sa.String(100), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_hitl_approvals_tenant_id", "hitl_approvals", ["tenant_id"])
    op.create_index("ix_hitl_approvals_rental_id", "hitl_approvals", ["rental_id"])
    op.create_index("ix_hitl_approvals_conversation_id", "hitl_approvals", ["conversation_id"])
    op.create_index("ix_hitl_approvals_agent_slug", "hitl_approvals", ["agent_slug"])
    op.create_index("ix_hitl_approvals_status", "hitl_approvals", ["status"])

    op.create_table(
        "interviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rental_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("candidate_name", sa.String(200), nullable=False),
        sa.Column("role_title", sa.String(200), nullable=False),
        sa.Column("interview_stage", sa.String(80), nullable=False, server_default="technical_round"),
        sa.Column("interviewer_emails", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="45"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("meeting_link", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="proposed"),
        sa.Column("invitation_draft", sa.Text(), nullable=False, server_default=""),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_interviews_tenant_id", "interviews", ["tenant_id"])
    op.create_index("ix_interviews_rental_id", "interviews", ["rental_id"])
    op.create_index("ix_interviews_candidate_id", "interviews", ["candidate_id"])

    op.create_table(
        "onboarding_workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "rental_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_rentals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "candidate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("candidates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("employee_name", sa.String(200), nullable=False),
        sa.Column("employee_email", sa.String(255), nullable=True),
        sa.Column("role_title", sa.String(200), nullable=False),
        sa.Column("department", sa.String(120), nullable=False, server_default="Engineering"),
        sa.Column("start_date", sa.String(40), nullable=True),
        sa.Column("current_stage", sa.String(60), nullable=False, server_default="document_collection"),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "documents_status_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("checklist_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column(
            "it_provisioning_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "team_allocation_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("training_plan_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_onboarding_workflows_tenant_id", "onboarding_workflows", ["tenant_id"])
    op.create_index("ix_onboarding_workflows_rental_id", "onboarding_workflows", ["rental_id"])
    op.create_index("ix_onboarding_workflows_candidate_id", "onboarding_workflows", ["candidate_id"])

    # Grant permissions to non-superuser runtime role & apply FORCE RLS
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
