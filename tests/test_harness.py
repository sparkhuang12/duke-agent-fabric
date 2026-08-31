from __future__ import annotations

import pytest
from conftest import ScriptedChatModel
from langchain_core.messages import AIMessage

from duke_harness.domain import ApprovalRequest, Principal, RunRequest, RunStatus
from duke_harness.models.router import ModelRouter
from duke_harness.resilience.errors import ContextAccessDeniedError
from duke_harness.runtime import Runtime


def _runtime(settings, responses: list[AIMessage]) -> Runtime:
    model = ScriptedChatModel(responses)
    return Runtime(settings, models=ModelRouter(settings, models={"fake": model}, sleep=lambda _: None))


def test_run_pauses_for_approval_and_resumes(settings) -> None:
    runtime = _runtime(settings, [AIMessage(content="待审批公文草稿")])
    principal = Principal(tenant_id="tenant", user_id="alice", roles=["user"])
    try:
        record = runtime.runner.start(
            principal,
            RunRequest(agent_id="document", thread_id="thread-one", input="写一份通知", idempotency_key="request-1"),
        )
        assert record.status == RunStatus.waiting_approval
        assert record.output == "待审批公文草稿"
        assert runtime.contexts.load(record.address, "通知").recent_messages == []

        reviewer = Principal(tenant_id="tenant", user_id="reviewer", roles=["approver"])
        completed = runtime.runner.resume(reviewer, record.run_id, ApprovalRequest(approved=True, comment="通过"))
        assert completed.status == RunStatus.completed
        assert [item.role for item in runtime.contexts.load(record.address, "通知").recent_messages] == [
            "user",
            "assistant",
        ]

        same = runtime.runner.start(
            principal,
            RunRequest(agent_id="document", thread_id="thread-one", input="写一份通知", idempotency_key="request-1"),
        )
        assert same.run_id == record.run_id
    finally:
        runtime.close()


def test_tool_loop_is_policy_checked(settings) -> None:
    tool_call = AIMessage(
        content="",
        tool_calls=[{"name": "search_knowledge", "args": {"query": "权限", "limit": 2}, "id": "call-1"}],
    )
    runtime = _runtime(settings, [tool_call, AIMessage(content="找到授权范围内的资料")])
    try:
        record = runtime.runner.start(
            Principal(tenant_id="tenant", user_id="alice", roles=["user"]),
            RunRequest(agent_id="search", thread_id="thread-search", input="搜索权限资料"),
        )
        assert record.status == RunStatus.completed
        assert record.usage["tool_calls"] == 1
        assert len(record.policy_decisions) == 4
        assert all(decision.allow for decision in record.policy_decisions)
    finally:
        runtime.close()


def test_confidential_run_requires_security_approval(settings) -> None:
    runtime = _runtime(settings, [AIMessage(content="保密检索结果")])
    try:
        record = runtime.runner.start(
            Principal(tenant_id="tenant", user_id="alice", roles=["user"], clearance="confidential"),
            RunRequest(
                agent_id="search",
                thread_id="classified-search",
                input="检索机密资料",
                security_level="confidential",
            ),
        )
        assert record.status == RunStatus.waiting_approval
        reviewer = Principal(
            tenant_id="tenant",
            user_id="reviewer",
            roles=["security_approver"],
            clearance="secret",
        )
        completed = runtime.runner.resume(
            reviewer,
            record.run_id,
            ApprovalRequest(approved=True, comment="密级与内容已核验"),
        )
        assert completed.status == RunStatus.completed
        assert completed.metadata["approval"]["reviewer_id"] == "reviewer"
    finally:
        runtime.close()


def test_long_term_memory_is_explicit_and_approved(settings) -> None:
    runtime = _runtime(settings, [AIMessage(content="记住这个项目决定")])
    owner = Principal(tenant_id="tenant", user_id="alice", roles=["user"])
    try:
        record = runtime.runner.start(
            owner,
            RunRequest(
                agent_id="search",
                thread_id="long-memory",
                input="记录架构决定",
                memory_scope="long_term",
            ),
        )
        assert record.status == RunStatus.waiting_approval
        with pytest.raises(ContextAccessDeniedError):
            runtime.runner.resume(owner, record.run_id, ApprovalRequest(approved=True))

        reviewer = Principal(
            tenant_id="tenant",
            user_id="reviewer",
            roles=["approver"],
            clearance="internal",
        )
        completed = runtime.runner.resume(reviewer, record.run_id, ApprovalRequest(approved=True))
        assert completed.status == RunStatus.completed
        snapshot = runtime.contexts.load(record.address, "架构")
        assert len(snapshot.memories) == 1
        assert snapshot.memories[0].metadata["approved"] is True
    finally:
        runtime.close()


def test_unconfigured_model_returns_structured_failure(settings) -> None:
    settings.model_name = ""
    runtime = Runtime(settings)
    try:
        record = runtime.runner.start(
            Principal(tenant_id="tenant", user_id="alice", roles=["user"]),
            RunRequest(agent_id="search", input="hello"),
        )
        assert record.status == RunStatus.failed
        assert record.error is not None
        assert record.error.code == "model_not_configured"
        assert record.error.retryable is False
    finally:
        runtime.close()
