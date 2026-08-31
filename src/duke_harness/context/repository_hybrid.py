from __future__ import annotations

from datetime import datetime
from typing import Any

from duke_harness.context.models import MemoryItem, StoredMessage
from duke_harness.context.repository import ContextRepository
from duke_harness.context.repository_mysql import MySQLLongTermRepository
from duke_harness.context.repository_redis import RedisShortTermRepository
from duke_harness.domain import ContextAddress, RunRecord


class HybridContextRepository(ContextRepository):
    """Redis short-term context plus MySQL long-term memory/run/audit storage."""

    def __init__(self, *, short_term: RedisShortTermRepository, long_term: MySQLLongTermRepository):
        self.short_term = short_term
        self.long_term = long_term

    def append_message(
        self,
        address: ContextAddress,
        *,
        role: str,
        content: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> StoredMessage:
        return self.short_term.append_message(address, role=role, content=content, run_id=run_id, metadata=metadata)

    def recent_messages(self, address: ContextAddress, limit: int) -> list[StoredMessage]:
        return self.short_term.recent_messages(address, limit)

    def message_count(self, address: ContextAddress) -> int:
        return self.short_term.message_count(address)

    def get_summary(self, address: ContextAddress) -> str:
        return self.short_term.get_summary(address)

    def set_summary(self, address: ContextAddress, summary: str) -> None:
        self.short_term.set_summary(address, summary)

    def add_memory(
        self,
        address: ContextAddress,
        *,
        content: str,
        kind: str = "episodic",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        return self.long_term.add_memory(address, content=content, kind=kind, importance=importance, metadata=metadata)

    def search_memories(self, address: ContextAddress, query: str, limit: int) -> list[MemoryItem]:
        return self.long_term.search_memories(address, query, limit)

    def save_run(self, record: RunRecord, idempotency_key: str | None = None) -> RunRecord:
        return self.long_term.save_run(record, idempotency_key)

    def get_run(self, run_id: str) -> RunRecord | None:
        return self.long_term.get_run(run_id)

    def get_idempotent_run(self, address: ContextAddress, key: str) -> RunRecord | None:
        return self.long_term.get_idempotent_run(address, key)

    def list_pending_runs(self, tenant_id: str, limit: int) -> list[RunRecord]:
        return self.long_term.list_pending_runs(tenant_id, limit)

    def expire_pending_runs(self, cutoff: datetime, *, dry_run: bool = True) -> int:
        return self.long_term.expire_pending_runs(cutoff, dry_run=dry_run)

    def append_audit(self, event: dict[str, Any]) -> None:
        self.long_term.append_audit(event)

    def ready(self) -> bool:
        return self.short_term.ready() and self.long_term.ready()

    def prune_retention(
        self,
        short_term_cutoff: datetime,
        long_term_cutoff: datetime,
        *,
        dry_run: bool = True,
    ) -> dict[str, int]:
        return {
            "messages": 0,
            **self.long_term.prune_before(short_term_cutoff, long_term_cutoff, dry_run=dry_run),
        }

    def close(self) -> None:
        self.short_term.close()
        self.long_term.close()
