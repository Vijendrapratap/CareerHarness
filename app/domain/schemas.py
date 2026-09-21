"""Pydantic schemas for API request and response validation."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str


class KeySaveRequest(BaseModel):
    provider: Literal["openai", "anthropic", "gemini", "openrouter"]
    api_key: str = Field(..., min_length=8, description="Raw provider API key")
    is_default: bool = True


class KeyResponse(BaseModel):
    id: str
    provider: str
    masked_preview: str
    status: str
    is_default: bool
    last_validated_at: Optional[datetime] = None


class RunCreateRequest(BaseModel):
    agent_name: str
    goal: str
    tier: Literal["cheap", "mid", "frontier"] = "mid"


class RunResponse(BaseModel):
    id: str
    tenant_id: str
    agent_name: str
    goal: str
    status: str
    step_count: int
    pause_reason: Optional[str] = None


class ApprovalResolveRequest(BaseModel):
    approved: bool


class ApprovalResponse(BaseModel):
    id: str
    tenant_id: str
    run_id: str
    tool_name: str
    status: str
    resolved_at: Optional[datetime] = None
