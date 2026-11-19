from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from duke_harness.context.manager import ContextManager
from duke_harness.context.repository import SQLiteContextRepository
from duke_harness.domain import ContextAddress, RunRecord, RunStatus, utc_now


def test_agent_and_tenant_namespaces_are_isolated(tmp_path: Path) -> None:
    repository = SQLiteContextRepository(tmp_path / "context.db")
    manager = ContextManager(repository)
    document = ContextAddress(tenant_id="tenant-a", user_id="alice", agent_id="document", thread_id="same-thread")
    policy = ContextAddress(tenant_id="tenant-a", user_id="alice", agent_id="policy", thread_id="same-thread")
    other_tenant = ContextAddress(tenant_id="tenant-b", user_id="alice", agent_id="document", thread_id="same-thread")

    manager.record_turn(document, "run-1", "机密预算是多少？", "预算内容仅属于 document 上下文")
    repository.add_memory(document, content="document-private-memory", kind="fact")

    assert "预算内容" in manager.load(document, "预算").recent_messages[-1].content
    assert manager.load(policy, "预算").recent_messages == []
    assert manager.load(policy, "memory").memories == []
    assert manager.load(other_tenant, "预算").recent_messages == []
    assert document.namespace != policy.namespace != other_tenant.namespace


def test_context_budget_keeps_recent_messages_without_cross_namespace_reads(tmp_path: Path) -> None:
    repository = SQLiteContextRepository(tmp_path / "context.db")
    manager = ContextManager(repository, recent_messages=4, max_chars=120, summary_chars=40)
    address = ContextAddress(tenant_id="t", user_id="u", agent_id="search", thread_id="thread")
    for index in range(6):
        manager.record_turn(address, f"run-{index}", f"question-{index}-" + "x" * 30, f"answer-{index}-" + "y" * 30)

    snapshot = manager.load(address, "question")
    assert snapshot.truncated is True
    assert snapshot.char_count <= 120
    assert all(item.run_id.startswith("run-") for item in snapshot.recent_messages)


def test_context_retention_supports_dry_run_before_delete(tmp_path: Path) -> None:
    repository = SQLiteContextRepository(tmp_path / "context.db")
    manager = ContextManager(repository)
    address = ContextAddress(tenant_id="t", user_id="u", agent_id="search", thread_id="retention")
    manager.record_turn(address, "run", "question", "answer")
    repository.add_memory(address, content="memory")
    cutoff = utc_now() + timedelta(days=1)

    expected = {"messages": 2, "run_payloads_scrubbed": 0, "memories": 1, "runs": 0, "audit_events": 0}
    assert repository.prune_retention(cutoff, cutoff, dry_run=True) == expected
    assert len(manager.load(address, "memory").recent_messages) == 2
    assert repository.prune_retention(cutoff, cutoff, dry_run=False) == expected
    assert manager.load(address, "memory").recent_messages == []


def test_context_filters_items_after_clearance_is_reduced(tmp_path: Path) -> None:
    repository = SQLiteContextRepository(tmp_path / "context.db")
    manager = ContextManager(repository)
    address = ContextAddress(tenant_id="t", user_id="u", agent_id="search", thread_id="classified")
    manager.record_turn(
        address,
        "run",
        "confidential input",
        "confidential output",
        security_level="confidential",
    )
    repository.add_memory(
        address,
        content="confidential memory",
        metadata={"security_level": "confidential"},
    )

    assert manager.load(address, "confidential", clearance="internal").recent_messages == []
    assert manager.load(address, "confidential", clearance="internal").memories == []
    assert len(manager.load(address, "confidential", clearance="confidential").recent_messages) == 2


def test_stale_pending_approval_is_expired_by_maintenance(tmp_path: Path) -> None:
    repository = SQLiteContextRepository(tmp_path / "context.db")
    address = ContextAddress(tenant_id="t", user_id="u", agent_id="document", thread_id="approval")
    record = RunRecord(
        run_id="run-expiring",
        address=address,
        status=RunStatus.waiting_approval,
        input="draft",
    )
    repository.save_run(record)
    stale_at = utc_now() - timedelta(days=8)
    record.updated_at = stale_at
    with repository._connect() as connection:  # noqa: SLF001 - repository retention integration test
        connection.execute(
            "UPDATE harness_runs SET record_json = ?, updated_at = ? WHERE run_id = ?",
            (record.model_dump_json(), stale_at.isoformat(), record.run_id),
        )

    cutoff = utc_now() - timedelta(days=7)
    assert repository.expire_pending_runs(cutoff, dry_run=True) == 1
    assert repository.get_run(record.run_id).status == RunStatus.waiting_approval  # type: ignore[union-attr]
    assert repository.expire_pending_runs(cutoff, dry_run=False) == 1
    expired = repository.get_run(record.run_id)
    assert expired is not None
    assert expired.status == RunStatus.failed
    assert expired.error is not None
    assert expired.error.code == "approval_expired"


def test_short_term_run_payload_is_scrubbed_after_seven_days(tmp_path: Path) -> None:
    repository = SQLiteContextRepository(tmp_path / "context.db")
    address = ContextAddress(tenant_id="t", user_id="u", agent_id="search", thread_id="short-run")
    stale_at = utc_now() - timedelta(days=8)
    record = RunRecord(
        run_id="run-short-retention",
        address=address,
        status=RunStatus.completed,
        input="sensitive short-lived input",
        output="sensitive short-lived output",
        metadata={"user_supplied": "must be removed"},
        created_at=stale_at,
        updated_at=stale_at,
    )
    repository.save_run(record)
    retained = RunRecord(
        run_id="run-approved-long-retention",
        address=address,
        status=RunStatus.completed,
        input="approved long-term input",
        output="approved long-term output",
        memory_scope="long_term",
        created_at=stale_at,
        updated_at=stale_at,
    )
    repository.save_run(retained)
    with repository._connect() as connection:  # noqa: SLF001 - repository retention integration test
        connection.execute(
            "UPDATE harness_runs SET created_at = ?, updated_at = ? WHERE run_id IN (?, ?)",
            (stale_at.isoformat(), stale_at.isoformat(), record.run_id, retained.run_id),
        )

    short_cutoff = utc_now() - timedelta(days=7)
    long_cutoff = utc_now() - timedelta(days=365)
    dry_run = repository.prune_retention(short_cutoff, long_cutoff, dry_run=True)
    assert dry_run["run_payloads_scrubbed"] == 1
    assert repository.get_run(record.run_id).input == "sensitive short-lived input"  # type: ignore[union-attr]
    applied = repository.prune_retention(short_cutoff, long_cutoff, dry_run=False)
    assert applied["run_payloads_scrubbed"] == 1
    scrubbed = repository.get_run(record.run_id)
    assert scrubbed is not None
    assert scrubbed.input == ""
    assert scrubbed.output == ""
    assert "user_supplied" not in scrubbed.metadata
    assert "payload_scrubbed_at" in scrubbed.metadata["retention"]
    assert repository.get_run(retained.run_id).input == "approved long-term input"  # type: ignore[union-attr]


def test_long_approved_draft_keeps_instruction_opening_and_deadline(tmp_path: Path) -> None:
    manager = ContextManager(SQLiteContextRepository(tmp_path / "drafts.db"), max_chars=110, recent_messages=4)
    address = ContextAddress(tenant_id="t", user_id="u", agent_id="document", thread_id="draft")
    manager.record_turn(address, "old", "旧要求", "旧内容" * 80)
    manager.record_turn(address, "latest", "只修改报送日期", "各处室：" + "中间内容" * 100 + "截止十二月十日。")
    snapshot = manager.load(address, "改稿")
    assert snapshot.truncated and snapshot.char_count <= 110
    assert [message.run_id for message in snapshot.recent_messages] == ["latest", "latest"]
    prompt, draft = snapshot.recent_messages
    assert prompt.content == "只修改报送日期"
    assert draft.content.startswith("各处室：") and draft.content.endswith("截止十二月十日。")
    assert "中段省略" in draft.content


def test_summary_covers_turn_before_recent_window_without_restricted_content(tmp_path: Path) -> None:
    manager = ContextManager(SQLiteContextRepository(tmp_path / "drafts.db"), recent_messages=4)
    address = ContextAddress(tenant_id="t", user_id="u", agent_id="document", thread_id="draft")
    levels = ["internal", "internal", "confidential", "internal", "internal"]
    for index, level in enumerate(levels):
        manager.record_turn(address, str(index), f"input-{index}", f"draft-{index}", security_level=level)
    snapshot = manager.load(address, "", clearance="internal")
    assert "draft-1" in snapshot.summary
    assert "draft-2" not in snapshot.summary
    assert [item.run_id for item in snapshot.recent_messages] == ["3", "3", "4", "4"]
