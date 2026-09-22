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
    users: Mapped[list["User"]] = relationship(
        "User", back_populates="tenant", cascade="all, delete-orphan"
    )
    stories: Mapped[list["Story"]] = relationship(
        "Story", back_populates="tenant", cascade="all, delete-orphan"
    )
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
    connected_emails: Mapped[list["ConnectedEmail"]] = relationship(
        "ConnectedEmail", back_populates="tenant", cascade="all, delete-orphan"
    )
    scout_schedules: Mapped[list["ScoutSchedule"]] = relationship(
        "ScoutSchedule", back_populates="tenant", cascade="all, delete-orphan"
    )
    job_matches: Mapped[list["JobMatch"]] = relationship(
        "JobMatch", back_populates="tenant", cascade="all, delete-orphan"
    )
    batches: Mapped[list["Batch"]] = relationship(
        "Batch", back_populates="tenant", cascade="all, delete-orphan"
    )
    document_versions: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="tenant", cascade="all, delete-orphan"
    )
    application_audit_logs: Mapped[list["ApplicationAuditLog"]] = relationship(
        "ApplicationAuditLog", back_populates="tenant", cascade="all, delete-orphan"
    )
    applications_tracked: Mapped[list["ApplicationTrack"]] = relationship(
        "ApplicationTrack", back_populates="tenant", cascade="all, delete-orphan"
    )
    outreach_messages: Mapped[list["OutreachMessage"]] = relationship(
        "OutreachMessage", back_populates="tenant", cascade="all, delete-orphan"
    )
    inbound_emails: Mapped[list["InboundEmail"]] = relationship(
        "InboundEmail", back_populates="tenant", cascade="all, delete-orphan"
    )
    profile_sections: Mapped[list["ProfileSection"]] = relationship(
        "ProfileSection", back_populates="tenant", cascade="all, delete-orphan"
    )
    interview_events: Mapped[list["InterviewEvent"]] = relationship(
        "InterviewEvent", back_populates="tenant", cascade="all, delete-orphan"
    )



class ConnectedEmail(Base):
    """Connected mailbox for hiring-manager outreach and reply parsing (F6)."""
    __tablename__ = "connected_emails"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="gmail")  # gmail or outlook
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="connected_emails")


class ScoutSchedule(Base):
    """Automated and on-demand Scout scan scheduler (F7, RD-02, RD-03)."""
    __tablename__ = "scout_schedules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cadence: Mapped[str] = mapped_column(String(32), default="daily")  # daily (Free) or hourly (Pro)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_scans_today: Mapped[int] = mapped_column(Integer, default=0)
    last_manual_scan_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="scout_schedules")


class JobListing(Base):
    """Scouted job listings with portal classification and legitimacy flags (F8)."""
    __tablename__ = "job_listings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="Remote")
    salary_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    portal_type: Mapped[str] = mapped_column(String(64), default="greenhouse")  # greenhouse, lever, workday, direct
    is_ghost_job: Mapped[bool] = mapped_column(Boolean, default=False)
    ghost_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_job_listings_dedup", "company", "url", unique=True),
    )


class JobMatch(Base):
    """Candidate-specific matched jobs scored by Analyst agent (F8)."""
    __tablename__ = "job_matches"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    match_score: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 to 10.0
    why_matched: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(32), default="new"
    )  # new, saved, batch_queued, applied, dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="job_matches")
    job: Mapped["JobListing"] = relationship("JobListing")


class Batch(Base):
    """Batch apply group managing fan-out execution (F8, BA-01..04)."""
    __tablename__ = "batches"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    total_jobs: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(32), default="created"
    )  # created, previewing, approved, running, completed, partial_failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="batches")
    items: Mapped[list["BatchItem"]] = relationship(
        "BatchItem", back_populates="batch", cascade="all, delete-orphan"
    )


class BatchItem(Base):
    """Individual child task in a batch apply run (BA-02, RT-01)."""
    __tablename__ = "batch_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_version_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    cover_letter_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    apply_channel: Mapped[str] = mapped_column(
        String(32), default="ats_autofill"
    )  # ats_autofill, email_apply, handoff
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending, tailoring, tailored, applying, applied, failed, handoff_ready
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped["Batch"] = relationship("Batch", back_populates="items")
    job: Mapped["JobListing"] = relationship("JobListing")

    __table_args__ = (
        Index("ix_batch_item_idempotency", "tenant_id", "job_id", "apply_channel", unique=True),
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


class DocumentVersion(Base):
    """Immutable document version with lineage tree and outcome tracking (F10, VR-01..03, IT-06)."""
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_type: Mapped[str] = mapped_column(
        String(32), default="resume"
    )  # resume, cover_letter
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    raw_markdown: Mapped[str] = mapped_column(Text, default="")
    parent_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_master: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    target_role_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    diff_summary: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    is_immutable: Mapped[bool] = mapped_column(Boolean, default=True)

    # Conversion & outcome tracking ("3 sends, 1 interview")
    applications_count: Mapped[int] = mapped_column(Integer, default=0)
    interviews_count: Mapped[int] = mapped_column(Integer, default=0)
    rejections_count: Mapped[int] = mapped_column(Integer, default=0)
    offers_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="document_versions")
    parent: Mapped[Optional["DocumentVersion"]] = relationship(
        "DocumentVersion", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["DocumentVersion"]] = relationship(
        "DocumentVersion", back_populates="parent"
    )


class ApplicationAuditLog(Base):
    """Immutable audit trail for every submitted or handed-off application (F9, AT-07, VR-01)."""
    __tablename__ = "application_audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cover_letter_version_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    batch_item_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    channel: Mapped[str] = mapped_column(
        String(32), default="ats_autofill"
    )  # ats_autofill, email_apply, candidate_handoff
    status: Mapped[str] = mapped_column(
        String(32), default="submitted"
    )  # submitted, handoff_ready, failed
    bot_mitigation_tier: Mapped[int] = mapped_column(Integer, default=1)  # 1, 2, 3
    screening_answers: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    submission_payload_snapshot: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, default=dict)
    fallback_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confirmation_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    handoff_bundle_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="application_audit_logs")
    job: Mapped["JobListing"] = relationship("JobListing")
    resume_version: Mapped["DocumentVersion"] = relationship(
        "DocumentVersion", foreign_keys=[resume_version_id]
    )


class ScreeningQuestionAnswer(Base):
    """Verified answers for application screening questions (F9, AT-04)."""
    __tablename__ = "screening_question_answers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    source_bullet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ApplicationTrack(Base):
    """Application tracking with status lifecycle and silence detection (F11)."""
    __tablename__ = "applications_tracked"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_version_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    portal_type: Mapped[str] = mapped_column(String(64), default="greenhouse")
    status: Mapped[str] = mapped_column(
        String(32), default="applied", index=True
    )  # applied, acknowledged, interview, assessment, offer, rejected, ghosted, withdrawn
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_ghosted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="applications_tracked")
    job: Mapped["JobListing"] = relationship("JobListing")
    resume_version: Mapped[Optional["DocumentVersion"]] = relationship("DocumentVersion")


class OutreachMessage(Base):
    """Personalized hiring-manager outreach with daily rate cap enforcement (F11, GT-04)."""
    __tablename__ = "outreach_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("applications_tracked.id", ondelete="SET NULL"), nullable=True
    )
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_role: Mapped[str] = mapped_column(String(128), default="Hiring Manager")
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="draft", index=True
    )  # draft, pending_approval, sent, failed, rejected
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="outreach_messages")
    application: Mapped[Optional["ApplicationTrack"]] = relationship("ApplicationTrack")


class InboundEmail(Base):
    """Inbound recruiter/company emails with reply classification (F11, GT-05)."""
    __tablename__ = "inbound_emails"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(
        String(32), default="other", index=True
    )  # interview, assessment, rejection, request_info, other
    confidence_score: Mapped[float] = mapped_column(Float, default=0.95)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    application_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("applications_tracked.id", ondelete="SET NULL"), nullable=True
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="inbound_emails")
    application: Mapped[Optional["ApplicationTrack"]] = relationship("ApplicationTrack")


class User(Base):
    """Real Authentication user model (Phase 0, Email/Password + Argon2id)."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")


class Story(Base):
    """Candidate experience story bank for reflection and outreach (Phase 2, Profiler)."""
    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    situation: Mapped[str] = mapped_column(Text, nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    skills_demonstrated: Mapped[list] = mapped_column(PortableJSON, default=list)
    metrics: Mapped[list] = mapped_column(PortableJSON, default=list)
    verified_against_master: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="stories")


class CandidateJourney(Base):
    """Tracks the candidate's current stage in the light neumorphic journey."""
    __tablename__ = "candidate_journeys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    stage: Mapped[str] = mapped_column(String(32), nullable=False, default="counsel")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ProfileSection(Base):
    """Stores structured answers from candidate onboarding and counsel interview."""
    __tablename__ = "profile_sections"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section: Mapped[str] = mapped_column(String(64), nullable=False)
    step: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[dict] = mapped_column(PortableJSON, default=dict)
    input_mode: Mapped[str] = mapped_column(String(16), default="text")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="profile_sections")

    __table_args__ = (
        Index("ix_profile_sections_tenant_step", "tenant_id", "step", unique=True),
    )


class InterviewEvent(Base):
    """Calendar interview event detected from recruiter communication (Task 12)."""
    __tablename__ = "interview_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications_tracked.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reminder_24h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_1h_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="interview_events")
    application: Mapped["ApplicationTrack"] = relationship("ApplicationTrack")

    __table_args__ = (
        Index("ix_interview_events_app_starts", "application_id", "starts_at", unique=True),
    )



class JobFit(Base):
    """Latest fit evaluation of one job for one candidate (recomputed when their facts/skills change)."""
    __tablename__ = "job_fits"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 to 5.0
    verdict: Mapped[str] = mapped_column(String(16), nullable=False)  # apply, stretch, skip
    report: Mapped[dict] = mapped_column(PortableJSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    __table_args__ = (
        Index("ix_job_fits_tenant_job", "tenant_id", "job_id", unique=True),
    )
