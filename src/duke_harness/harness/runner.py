from __future__ import annotations

import hashlib
import time
from datetime import timedelta
from typing import Any

from langgraph.types import Command

from duke_harness.agents.registry import AgentRegistry
from duke_harness.context.repository import ContextRepository
from duke_harness.domain import (
    ApprovalRequest,
    ContextAddress,
    ErrorDetail,
    PolicyDecision,
    Principal,
    RunRecord,
    RunRequest,
    RunStatus,
    SecurityLevel,
    new_id,
    utc_now,
)
from duke_harness.policy.client import PolicyClient
from duke_harness.resilience.errors import ContextAccessDeniedError, HarnessError, RunNotFoundError
from duke_harness.resilience.run_locks import RunLockManager


class HarnessRunner:
    def __init__(
        self,
        *,
        graph: Any,
        repository: ContextRepository,
        agents: AgentRegistry,
        policies: PolicyClient,
        max_run_seconds: int,
        max_graph_steps: int,
        approval_ttl_seconds: int,
        run_locks: RunLockManager,
    ):
        self.graph = graph
        self.repository = repository
        self.agents = agents
        self.policies = policies
        self.max_run_seconds = max_run_seconds
        self.max_graph_steps = max_graph_steps
        self.approval_ttl_seconds = approval_ttl_seconds
        self.run_locks = run_locks

    @staticmethod
    def _checkpoint_id(record: RunRecord) -> str:
        digest = hashlib.sha256(f"{record.address.namespace}\x00{record.run_id}".encode()).hexdigest()
        return f"run_{digest[:48]}"

    def _config(self, record: RunRecord, agent_steps: int) -> dict[str, Any]:
        return {
            "configurable": {"thread_id": self._checkpoint_id(record)},
            "recursion_limit": min(self.max_graph_steps, agent_steps * 2 + 8),
        }

    def start(self, principal: Principal, request: RunRequest) -> RunRecord:
        agent = self.agents.require(request.agent_id)
        address = ContextAddress(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            agent_id=agent.id,
            thread_id=request.thread_id,
        )
        if request.idempotency_key:
            previous = self.repository.get_idempotent_run(address, request.idempotency_key)
            if previous is not None:
                return previous
        record = RunRecord(
            run_id=new_id("run"),
            address=address,
            status=RunStatus.running,
            input=request.input,
            trace_id=new_id("trace"),
            metadata=request.metadata,
            security_level=request.security_level,
            memory_scope=request.memory_scope,
        )
        saved = self.repository.save_run(record, request.idempotency_key)
        if saved.run_id != record.run_id:
            return saved
        started = time.monotonic()
        try:
            result = self.graph.invoke(
                {
                    "run_id": record.run_id,
                    "deadline_epoch": time.time() + self.max_run_seconds,
                    "input": request.input,
                    "principal": principal.model_dump(mode="json"),
                    "address": address.model_dump(mode="json"),
                    "agent": agent.model_dump(mode="json"),
                    "messages": [],
                    "policy_decisions": [],
                    "tool_call_count": 0,
                    "status": "running",
                    "security_level": request.security_level.value,
                    "memory_scope": request.memory_scope,
                    "requires_approval": agent.require_approval,
                },
                config=self._config(record, agent.max_steps),
            )
            record = self._apply_result(record, result)
        except Exception as exc:
            record.status = RunStatus.failed
            record.error = self._error_detail(exc)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        record.usage["elapsed_ms"] = elapsed_ms
        self.repository.save_run(record, request.idempotency_key)
        self._audit(record, "run.finished")
        return record

    def resume(self, principal: Principal, run_id: str, approval: ApprovalRequest) -> RunRecord:
        with self.run_locks.hold(run_id, ttl_seconds=self.max_run_seconds + 120):
            return self._resume_locked(principal, run_id, approval)

    def _resume_locked(self, principal: Principal, run_id: str, approval: ApprovalRequest) -> RunRecord:
        record = self.repository.get_run(run_id)
        if record is None:
            raise RunNotFoundError(run_id)
        if record.status != RunStatus.waiting_approval:
            return record
        if utc_now() > record.updated_at + timedelta(seconds=self.approval_ttl_seconds):
            record.status = RunStatus.failed
            record.error = ErrorDetail(
                code="approval_expired",
                message="the approval window expired with the short-term checkpoint",
                stage="approval",
            )
            self.repository.save_run(record)
            self._audit(record, "run.approval_expired")
            return record
        agent = self.agents.require(record.address.agent_id)
        decision = self.policies.decide(
            action="run.approve",
            principal=principal,
            address=record.address,
            agent=agent,
            resource={"security_level": record.security_level.value},
            context={"run_id": record.run_id},
        )
        if not decision.allow:
            raise ContextAccessDeniedError("principal is not authorized to approve this run")
        record.metadata["approval"] = {
            "reviewer_id": principal.user_id,
            "roles": principal.roles,
            "comment": approval.comment,
        }
        try:
            result = self.graph.invoke(
                Command(resume=approval.model_dump(mode="json")),
                config=self._config(record, agent.max_steps),
            )
            record = self._apply_result(record, result)
        except Exception as exc:
            record.status = RunStatus.failed
            record.error = self._error_detail(exc)
        self.repository.save_run(record)
        self._audit(record, "run.approval_resolved")
        return record

    def get(self, principal: Principal, run_id: str) -> RunRecord:
        record = self.repository.get_run(run_id)
        if record is None:
            raise RunNotFoundError(run_id)
        if record.address.tenant_id != principal.tenant_id or record.address.user_id != principal.user_id:
            raise ContextAccessDeniedError("run belongs to a different context namespace")
        agent = self.agents.require(record.address.agent_id)
        decision = self.policies.decide(
            action="run.read",
            principal=principal,
            address=record.address,
            agent=agent,
            resource={"security_level": record.security_level.value},
            context={"run_id": record.run_id},
        )
        if not decision.allow:
            raise ContextAccessDeniedError("principal is not authorized to read this run")
        return record

    def pending_approvals(self, principal: Principal, limit: int) -> list[RunRecord]:
        records = self.repository.list_pending_runs(principal.tenant_id, limit * 2)
        allowed: list[RunRecord] = []
        for record in records:
            if utc_now() > record.updated_at + timedelta(seconds=self.approval_ttl_seconds):
                continue
            agent = self.agents.require(record.address.agent_id)
            decision = self.policies.decide(
                action="run.approve",
                principal=principal,
                address=record.address,
                agent=agent,
                resource={"security_level": record.security_level.value},
                context={"run_id": record.run_id},
            )
            if decision.allow:
                allowed.append(record)
            if len(allowed) >= limit:
                break
        return allowed

    @staticmethod
    def _apply_result(record: RunRecord, result: dict[str, Any]) -> RunRecord:
        record.output = str(result.get("output", record.output))
        record.policy_decisions = [
            PolicyDecision.model_validate(item) for item in result.get("policy_decisions", record.policy_decisions)
        ]
        record.security_level = SecurityLevel(result.get("security_level", record.security_level.value))
        if result.get("__interrupt__"):
            record.status = RunStatus.waiting_approval
        else:
            record.status = RunStatus(result.get("status", "failed"))
            if record.status == RunStatus.denied:
                record.error = ErrorDetail(
                    code="policy_or_approval_denied",
                    message=str(result.get("denial_reason", "operation denied")),
                    stage="policy",
                )
        record.usage["tool_calls"] = int(result.get("tool_call_count", 0))
        return record

    @staticmethod
    def _error_detail(exc: Exception) -> ErrorDetail:
        if isinstance(exc, HarnessError):
            return ErrorDetail(code=exc.code, message=str(exc), retryable=exc.retryable, stage=exc.stage)
        return ErrorDetail(
            code="unhandled_harness_error",
            message="an unexpected internal harness error occurred",
            retryable=False,
            stage="runtime",
            details={"exception_type": type(exc).__name__},
        )

    def _audit(self, record: RunRecord, event_type: str) -> None:
        self.repository.append_audit(
            {
                "event_type": event_type,
                "run_id": record.run_id,
                "trace_id": record.trace_id,
                "tenant_id": record.address.tenant_id,
                "user_id": record.address.user_id,
                "agent_id": record.address.agent_id,
                "thread_id_hash": hashlib.sha256(record.address.thread_id.encode()).hexdigest(),
                "status": record.status.value,
                "input_chars": len(record.input),
                "output_chars": len(record.output),
                "error_code": record.error.code if record.error else None,
            }
        )
