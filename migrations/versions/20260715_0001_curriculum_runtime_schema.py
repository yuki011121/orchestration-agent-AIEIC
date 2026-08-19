"""curriculum runtime schema

Revision ID: 20260715_0001
Revises:
Create Date: 2026-07-15
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260715_0001"
down_revision = None
branch_labels = None
depends_on = None


def json_type() -> sa.types.TypeEngine:
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "courses",
        sa.Column("course_id", sa.String(length=128), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("term", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "labs",
        sa.Column("lab_id", sa.String(length=128), primary_key=True),
        sa.Column("course_id", sa.String(length=128), sa.ForeignKey("courses.course_id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("active_package_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "curriculum_drafts",
        sa.Column("lab_id", sa.String(length=128), primary_key=True),
        sa.Column("course_id", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("spec_markdown", sa.Text(), nullable=False),
        sa.Column("quiz_json", json_type(), nullable=False),
        sa.Column("rubric_json", json_type(), nullable=False),
        sa.Column("learning_objectives_json", json_type(), nullable=False),
        sa.Column("difficulty", sa.String(length=64), nullable=False),
        sa.Column("estimated_duration_min", sa.Integer(), nullable=False),
        sa.Column("material_content", sa.Text(), nullable=True),
        sa.Column("agent_instructions", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.String(length=32), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approval_notes", sa.Text(), nullable=True),
        sa.Column("feedback_history_json", json_type(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "lab_packages",
        sa.Column("package_id", sa.String(length=255), primary_key=True),
        sa.Column("course_id", sa.String(length=128), nullable=False),
        sa.Column("lab_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("spec_markdown", sa.Text(), nullable=False),
        sa.Column("quiz_json", json_type(), nullable=False),
        sa.Column("rubric_json", json_type(), nullable=False),
        sa.Column("tutor_instructions", sa.Text(), nullable=True),
        sa.Column("assessment_config_json", json_type(), nullable=False),
        sa.Column("source_artifacts_json", json_type(), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("course_id", "lab_id", "version", name="uq_lab_package_version"),
    )
    op.create_table(
        "events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("course_id", sa.String(length=128), nullable=True),
        sa.Column("lab_id", sa.String(length=128), nullable=True),
        sa.Column("student_id", sa.String(length=128), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("submission_id", sa.String(length=128), nullable=True),
        sa.Column("job_id", sa.String(length=128), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=True),
        sa.Column("actor_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", json_type(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("lab_packages")
    op.drop_table("curriculum_drafts")
    op.drop_table("labs")
    op.drop_table("courses")
