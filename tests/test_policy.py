from __future__ import annotations

import httpx

from duke_harness.domain import AgentSpec, ContextAddress, Principal
from duke_harness.policy.client import PolicyClient


def _models():
    principal = Principal(tenant_id="tenant", user_id="user", roles=["user"])
    address = ContextAddress(tenant_id="tenant", user_id="user", agent_id="search", thread_id="thread")
    agent = AgentSpec(id="search", name="Search", description="", system_prompt="", allowed_tools=["safe"])
    return principal, address, agent


def test_opa_decision_is_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"decision_id": "decision-1", "result": {"allow": True, "reasons": [], "obligations": {}}},
        )

    client = PolicyClient(
        base_url="http://opa",
        decision_path="/v1/data/duke/harness/decision",
        transport=httpx.MockTransport(handler),
    )
    principal, address, agent = _models()
    decision = client.decide(action="agent.invoke", principal=principal, address=address, agent=agent)
    assert decision.allow is True
    assert decision.decision_id == "decision-1"
    assert decision.source == "opa"


def test_fail_closed_and_embedded_tool_allowlist() -> None:
    def unavailable(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    principal, address, agent = _models()
    closed = PolicyClient(
        base_url="http://opa",
        decision_path="/decision",
        failure_mode="closed",
        transport=httpx.MockTransport(unavailable),
    )
    assert closed.decide(action="agent.invoke", principal=principal, address=address, agent=agent).allow is False

    embedded = PolicyClient(
        base_url="http://opa",
        decision_path="/decision",
        embedded_development_fallback=True,
        transport=httpx.MockTransport(unavailable),
    )
    denied = embedded.decide(
        action="tool.call",
        principal=principal,
        address=address,
        agent=agent,
        resource={"tool_name": "shell"},
    )
    assert denied.allow is False
    assert denied.source == "embedded"
