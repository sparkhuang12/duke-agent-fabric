from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class StoredMessage(BaseModel):
    id: str
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    created_at: datetime
    run_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryItem(BaseModel):
    id: str
    kind: Literal["episodic", "fact", "preference", "decision"] = "episodic"
    content: str
    importance: float = Field(default=0.5, ge=0, le=1)
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextSnapshot(BaseModel):
    namespace: str
    summary: str = ""
    recent_messages: list[StoredMessage] = Field(default_factory=list)
    memories: list[MemoryItem] = Field(default_factory=list)
    truncated: bool = False
    char_count: int = 0
