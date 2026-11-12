"""Add optimization and honest baseline-vs-optimized telemetry columns to token_usage

Revision ID: 20261111_0004
Revises: 20261111_0003
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261111_0004"
down_revision: Union[str, None] = "20261111_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "token_usage",
        sa.Column("baseline_input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "token_usage",
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "token_usage",
        sa.Column("tool_calls_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "token_usage",
        sa.Column("optimization_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "token_usage",
        sa.Column(
            "optimization_methods_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("token_usage", "optimization_methods_json")
    op.drop_column("token_usage", "optimization_enabled")
    op.drop_column("token_usage", "tool_calls_count")
    op.drop_column("token_usage", "duration_ms")
    op.drop_column("token_usage", "baseline_input_tokens")
