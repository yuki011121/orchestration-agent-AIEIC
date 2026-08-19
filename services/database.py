"""Database primitives for the integrated AIEIC runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.types import JSON


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    return database_url


def json_type() -> Any:
    return JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class CourseRecord(Base):
    __tablename__ = "courses"

    course_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    term: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class LabRecord(Base):
    __tablename__ = "labs"

    lab_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    course_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("courses.course_id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), default="pre_lab", nullable=False)
    active_package_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class CurriculumDraftRecord(Base):
    __tablename__ = "curriculum_drafts"

    lab_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    quiz_json: Mapped[list[dict[str, Any]]] = mapped_column(json_type(), nullable=False)
    rubric_json: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False)
    learning_objectives_json: Mapped[list[str]] = mapped_column(json_type(), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(64), nullable=False)
    estimated_duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    material_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approval_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_history_json: Mapped[list[dict[str, Any]]] = mapped_column(
        json_type(),
        default=list,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LabPackageRecord(Base):
    __tablename__ = "lab_packages"
    __table_args__ = (
        UniqueConstraint("course_id", "lab_id", "version", name="uq_lab_package_version"),
    )

    package_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    course_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lab_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="approved", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    quiz_json: Mapped[list[dict[str, Any]]] = mapped_column(json_type(), nullable=False)
    rubric_json: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False)
    tutor_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_config_json: Mapped[dict[str, Any]] = mapped_column(
        json_type(),
        default=dict,
        nullable=False,
    )
    source_artifacts_json: Mapped[list[dict[str, Any]]] = mapped_column(
        json_type(),
        default=list,
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class EventRecord(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    course_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lab_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    student_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    submission_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(json_type(), default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


def build_engine(database_url: str) -> Engine:
    if not database_url:
        raise ValueError("DATABASE_URL is required for curriculum package publishing")
    return create_engine(normalize_database_url(database_url), pool_pre_ping=True)


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def ensure_schema(engine: Engine) -> None:
    Base.metadata.create_all(engine)
