"""SQLAlchemy database models with tenant isolation."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PortableJSON(TypeDecorator):
    """JSON type that works seamlessly on both PostgreSQL (JSONB) and SQLite (JSON)."""
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="free")  # "free" or "pro"
    trusted_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    # Relationships with cascade delete (KY-05)
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey", back_populates="tenant", cascade="all, delete-orphan"
    )
    runs: Mapped[list["Run"]] = relationship(
        "Run", back_populates="tenant", cascade="all, delete-orphan"
    )
    outbox_events: Mapped[list["OutboxEvent"]] = relationship(
        "OutboxEvent", back_populates="tenant", cascade="all, delete-orphan"
    )
    role_selections: Mapped[list["RoleSelection"]] = relationship(
        "RoleSelection", back_populates="tenant", cascade="all, delete-orphan"
    )
    resume_parses: Mapped[list["ResumeParse"]] = relationship(
        "ResumeParse", back_populates="tenant", cascade="all, delete-orphan"
    )
    linkedin_profiles: Mapped[list["LinkedInProfile"]] = relationship(
        "LinkedInProfile", back_populates="tenant", cascade="all, delete-orphan"
    )
    todo_items: Mapped[list["TodoItem"]] = relationship(
        "TodoItem", back_populates="tenant", cascade="all, delete-orphan"
    )
    readiness_scores: Mapped[list["ReadinessScore"]] = relationship(
        "ReadinessScore", back_populates="tenant", cascade="all, delete-orphan"
    )
    consents: Mapped[list["Consent"]] = relationship(
        "Consent", back_populates="tenant", cascade="all, delete-orphan"
    )


class RoleCatalog(Base):
    """System-wide predefined role catalog with requirement baselines."""
    __tablename__ = "role_catalog"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(PortableJSON, default=list)
    baseline_skills: Mapped[list[str]] = mapped_column(PortableJSON, default=list)
    is_leadership: Mapped[bool] = mapped_column(Boolean, default=False)


class RoleSelection(Base):
    """Candidate selected target roles (Max 3, +1 with management flag, F2)."""
    __tablename__ = "role_selections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1 = priority role
    mgmt_lens: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="role_selections")

    __table_args__ = (
        Index("ix_role_selection_tenant_role", "tenant_id", "role_id", unique=True),
    )


class ResumeParse(Base):
    """Parsed structured resume data (F3)."""
    __tablename__ = "resume_parses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    # AT-06: extracted_skills defaults to verified=False
    extracted_skills: Mapped[list[Dict[str, Any]]] = mapped_column(PortableJSON, default=list)
    metrics: Mapped[list[Dict[str, Any]]] = mapped_column(PortableJSON, default=list)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="resume_parses")


class LinkedInProfile(Base):
    """Captured LinkedIn profile data (F4)."""
    __tablename__ = "linkedin_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    headline: Mapped[str] = mapped_column(String(255), default="")
    about: Mapped[str] = mapped_column(Text, default="")
    experience_entries: Mapped[list[Dict[str, Any]]] = mapped_column(PortableJSON, default=list)
    skills: Mapped[list[str]] = mapped_column(PortableJSON, default=list)
    source_mode: Mapped[str] = mapped_column(String(32), default="paste")  # paste or url_fetch
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="linkedin_profiles")


class GapReport(Base):
    """Gap analysis between candidate assets and target roles (F5)."""
    __tablename__ = "gap_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    presentation_gaps: Mapped[list[Dict[str, Any]]] = mapped_column(PortableJSON, default=list)
    skill_gaps: Mapped[list[Dict[str, Any]]] = mapped_column(PortableJSON, default=list)
    linkedin_gaps: Mapped[list[Dict[str, Any]]] = mapped_column(PortableJSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TodoItem(Base):
    """Actionable fix item emitted by Gap Engine (F5)."""
    __tablename__ = "todo_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)  # critical, major, minor
    issue_text: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False)
    fix_draft: Mapped[str] = mapped_column(Text, nullable=False)
    source_bullet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # GE-01 citability
    has_unverified_metric: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(
        String(32), default="open"
    )  # open, accepted, edited, dismissed
    dismiss_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="todo_items")


class ReadinessScore(Base):
    """Front-Face Score snapshot (0–100) (F5/F7)."""
    __tablename__ = "readiness_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    ats_parse_score: Mapped[int] = mapped_column(Integer, default=0)     # max 15
    metric_coverage_score: Mapped[int] = mapped_column(Integer, default=0) # max 20
    honest_keyword_score: Mapped[int] = mapped_column(Integer, default=0)  # max 15
    linkedin_headline_about_score: Mapped[int] = mapped_column(Integer, default=0) # max 20
    experience_mirroring_score: Mapped[int] = mapped_column(Integer, default=0) # max 15
    critical_todos_cleared_score: Mapped[int] = mapped_column(Integer, default=0) # max 15
    is_capped_at_69: Mapped[bool] = mapped_column(Boolean, default=False) # GE-03 rule
    cap_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="readiness_scores")


class Consent(Base):
    """Explicit legal consent record before external actions (F4/F6, CT-04)."""
    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consent_type: Mapped[str] = mapped_column(String(64), nullable=False)  # linkedin_fetch, email_connect
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="consents")


class ApiKey(Base):
    """Encrypted BYOK credentials.

    Enforces KY-01: Only encrypted_key_b64 and nonce_b64 are persisted.
    Plaintext never touches DB columns.
    """
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # openai, anthropic, gemini, openrouter
    encrypted_key_b64: Mapped[str] = mapped_column(Text, nullable=False)
    nonce_b64: Mapped[str] = mapped_column(String(64), nullable=False)
    masked_preview: Mapped[str] = mapped_column(String(32), nullable=False)  # sk-...4f2a
    status: Mapped[str] = mapped_column(String(32), default="valid")  # valid, invalid, no_credits
    is_default: Mapped[bool] = mapped_column(Boolean, default=True)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="api_keys")

    __table_args__ = (
        Index("ix_api_keys_tenant_provider", "tenant_id", "provider", unique=True),
    )


class Run(Base):
    """An execution run for an agent (Harness context)."""
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="running"
    )  # running, awaiting_approval, completed, failed, paused
    step_count: Mapped[int] = mapped_column(Integer, default=0)
    current_plan: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    pause_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="runs")
    checkpoints: Mapped[list["Checkpoint"]] = relationship(
        "Checkpoint", back_populates="run", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        "Approval", back_populates="run", cascade="all, delete-orphan"
    )


class Checkpoint(Base):
    """PostgreSQL checkpoint snapshot for crash-resume recovery."""
    __tablename__ = "checkpoints"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state_snapshot: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped["Run"] = relationship("Run", back_populates="checkpoints")

    __table_args__ = (
        Index("ix_checkpoint_run_step", "run_id", "step_index", unique=True),
    )


class Approval(Base):
    """HITL Gate records for external tools requiring confirmation."""
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending, approved, rejected
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    run: Mapped["Run"] = relationship("Run", back_populates="approvals")


class OutboxEvent(Base):
    """Transactional Outbox table for reliable Redis Streams publishing."""
    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True
    )  # pending, published, failed
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="outbox_events")
