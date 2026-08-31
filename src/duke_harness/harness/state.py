from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class HarnessState(TypedDict, total=False):
    run_id: str
    deadline_epoch: float
    input: str
    principal: dict[str, Any]
    address: dict[str, Any]
    agent: dict[str, Any]
    messages: Annotated[list[AnyMessage], add_messages]
    output: str
    status: str
    denial_reason: str
    policy_decisions: list[dict[str, Any]]
    tool_call_count: int
    approval: dict[str, Any]
    context_metadata: dict[str, Any]
    security_level: str
    memory_scope: str
    requires_approval: bool
