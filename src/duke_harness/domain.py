from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Principal(BaseModel):
    tenant_id: str
    user_id: str
    roles: list[str] = Field(default_factory=list)
    department: str = ""
    clearance: str = "internal"

    @field_validator("tenant_id", "user_id")
    @classmethod
    def safe_identifiers(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("identifier must be 1-128 safe characters")
        return value

    @field_validator("clearance")
    @classmethod
    def supported_clearance(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"public", "internal", "confidential", "secret"}:
            raise ValueError("unsupported clearance")
        return normalized


class SecurityLevel(str, Enum):
    public = "public"
    internal = "internal"
    confidential = "confidential"
    secret = "secret"


class ContextAddress(BaseModel):
    tenant_id: str
    user_id: str
    agent_id: str
    thread_id: str

    @field_validator("tenant_id", "user_id", "agent_id", "thread_id")
    @classmethod
    def safe_identifiers(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("identifier must be 1-128 safe characters")
        return value

    @property
    def namespace(self) -> str:
        raw = "\x00".join((self.tenant_id, self.user_id, self.agent_id, self.thread_id))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @property
    def checkpoint_thread_id(self) -> str:
        return f"ctx_{self.namespace[:48]}"


class AgentSpec(BaseModel):
    id: str
    name: str
    description: str
    system_prompt: str
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_roles: list[str] = Field(default_factory=lambda: ["user", "platform_admin"])
    skills: list[str] = Field(default_factory=list)
    require_approval: bool = True
    max_steps: int = Field(default=8, ge=2, le=50)

    @field_validator("id")
    @classmethod
    def safe_id(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("invalid agent id")
        return value


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    waiting_approval = "waiting_approval"
    completed = "completed"
    denied = "denied"
    failed = "failed"


class RunRequest(BaseModel):
    agent_id: str
    thread_id: str = Field(default_factory=lambda: new_id("thread"))
    input: str = Field(min_length=1, max_length=100_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=128)
    security_level: SecurityLevel = SecurityLevel.internal
    memory_scope: Literal["short_term", "long_term"] = "short_term"

    @field_validator("agent_id", "thread_id")
    @classmethod
    def safe_identifiers(cls, value: str) -> str:
        if not IDENTIFIER_PATTERN.fullmatch(value):
            raise ValueError("invalid identifier")
        return value


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    stage: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    allow: bool
    reasons: list[str] = Field(default_factory=list)
    obligations: dict[str, Any] = Field(default_factory=dict)
    decision_id: str = ""
    source: Literal["opa", "embedded", "failure"] = "opa"


class RunRecord(BaseModel):
    run_id: str
    address: ContextAddress
    status: RunStatus
    input: str
    output: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    trace_id: str = ""
    policy_decisions: list[PolicyDecision] = Field(default_factory=list)
    error: ErrorDetail | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    security_level: SecurityLevel = SecurityLevel.internal
    memory_scope: Literal["short_term", "long_term"] = "short_term"


class ApprovalRequest(BaseModel):
    approved: bool
    comment: str = Field(default="", max_length=4000)


class HealthStatus(BaseModel):
    status: Literal["ok", "degraded", "error"]
    checks: dict[str, Any]
