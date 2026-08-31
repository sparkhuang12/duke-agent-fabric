from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from duke_harness.context.models import MemoryItem, StoredMessage
from duke_harness.context.repository import ContextRepository, run_payload_needs_scrub, scrub_run_payload
from duke_harness.domain import ContextAddress, ErrorDetail, RunRecord, RunStatus, new_id, utc_now


class PostgresContextRepository(ContextRepository):
    """Legacy-compatible PostgreSQL repository; new production profiles use MySQL + Redis."""

    def __init__(self, database_url: str):
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - exercised in production image
            raise RuntimeError("install duke-agent-fabric[postgres] for PostgreSQL support") from exc
        self._dict_row = dict_row
        self._pool = ConnectionPool(database_url, min_size=1, max_size=10, open=True)
        self._initialize()

    def close(self) -> None:
        self._pool.close()

    def _initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS context_threads (
          namespace TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          thread_id TEXT NOT NULL,
          summary TEXT NOT NULL DEFAULT '',
          updated_at TIMESTAMPTZ NOT NULL,
          UNIQUE (tenant_id, user_id, agent_id, thread_id)
        );
        CREATE TABLE IF NOT EXISTS context_messages (
          id TEXT PRIMARY KEY,
          namespace TEXT NOT NULL REFERENCES context_threads(namespace) ON DELETE CASCADE,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          run_id TEXT NOT NULL,
          metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_messages_namespace_created
          ON context_messages(namespace, created_at DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_run_role
          ON context_messages(namespace, run_id, role);
        CREATE TABLE IF NOT EXISTS context_memories (
          id TEXT PRIMARY KEY,
          namespace TEXT NOT NULL REFERENCES context_threads(namespace) ON DELETE CASCADE,
          kind TEXT NOT NULL,
          content TEXT NOT NULL,
          importance DOUBLE PRECISION NOT NULL,
          metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memories_namespace
          ON context_memories(namespace, importance DESC, created_at DESC);
        CREATE TABLE IF NOT EXISTS harness_runs (
          run_id TEXT PRIMARY KEY,
          namespace TEXT NOT NULL,
          idempotency_key TEXT,
          record_json JSONB NOT NULL,
          status TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL,
          UNIQUE(namespace, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_runs_status_updated ON harness_runs(status, updated_at DESC);
        CREATE TABLE IF NOT EXISTS audit_events (
          id TEXT PRIMARY KEY,
          event_json JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL
        );
        """
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(schema)

    def _ensure_thread(self, cursor: Any, address: ContextAddress) -> None:
        cursor.execute(
            """INSERT INTO context_threads
               (namespace, tenant_id, user_id, agent_id, thread_id, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT(namespace) DO NOTHING""",
            (
                address.namespace,
                address.tenant_id,
                address.user_id,
                address.agent_id,
                address.thread_id,
                utc_now(),
            ),
        )

    def append_message(
        self,
        address: ContextAddress,
        *,
        role: str,
        content: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> StoredMessage:
        message = StoredMessage(
            id=new_id("msg"),
            role=role,  # type: ignore[arg-type]
            content=content,
            run_id=run_id,
            metadata=metadata or {},
            created_at=utc_now(),
        )
        with self._pool.connection() as connection, connection.cursor() as cursor:
            self._ensure_thread(cursor, address)
            cursor.execute(
                """INSERT INTO context_messages
                   (id, namespace, role, content, run_id, metadata_json, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT(namespace, run_id, role) DO NOTHING""",
                (
                    message.id,
                    address.namespace,
                    message.role,
                    message.content,
                    message.run_id,
                    json.dumps(message.metadata, ensure_ascii=False),
                    message.created_at,
                ),
            )
        return message

    def recent_messages(self, address: ContextAddress, limit: int) -> list[StoredMessage]:
        with self._pool.connection() as connection, connection.cursor(row_factory=self._dict_row) as cursor:
            cursor.execute(
                """SELECT * FROM context_messages WHERE namespace = %s
                   ORDER BY created_at DESC LIMIT %s""",
                (address.namespace, limit),
            )
            rows = cursor.fetchall()
        return [self._message(row) for row in reversed(rows)]

    def message_count(self, address: ContextAddress) -> int:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM context_messages WHERE namespace = %s", (address.namespace,))
            row = cursor.fetchone()
        return int(row[0] if row else 0)

    def get_summary(self, address: ContextAddress) -> str:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT summary FROM context_threads WHERE namespace = %s", (address.namespace,))
            row = cursor.fetchone()
        return str(row[0]) if row else ""

    def set_summary(self, address: ContextAddress, summary: str) -> None:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            self._ensure_thread(cursor, address)
            cursor.execute(
                "UPDATE context_threads SET summary = %s, updated_at = %s WHERE namespace = %s",
                (summary, utc_now(), address.namespace),
            )

    def add_memory(
        self,
        address: ContextAddress,
        *,
        content: str,
        kind: str = "episodic",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        item = MemoryItem(
            id=new_id("mem"),
            kind=kind,  # type: ignore[arg-type]
            content=content,
            importance=importance,
            metadata=metadata or {},
            created_at=utc_now(),
        )
        with self._pool.connection() as connection, connection.cursor() as cursor:
            self._ensure_thread(cursor, address)
            cursor.execute(
                """INSERT INTO context_memories
                   (id, namespace, kind, content, importance, metadata_json, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    item.id,
                    address.namespace,
                    item.kind,
                    item.content,
                    item.importance,
                    json.dumps(item.metadata, ensure_ascii=False),
                    item.created_at,
                ),
            )
        return item

    def search_memories(self, address: ContextAddress, query: str, limit: int) -> list[MemoryItem]:
        query_text = " ".join(token for token in query.split()[:8] if token)
        with self._pool.connection() as connection, connection.cursor(row_factory=self._dict_row) as cursor:
            if query_text:
                cursor.execute(
                    """SELECT * FROM context_memories
                       WHERE namespace = %s AND to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
                       ORDER BY importance DESC, created_at DESC LIMIT %s""",
                    (address.namespace, query_text, limit),
                )
            else:
                cursor.execute(
                    """SELECT * FROM context_memories WHERE namespace = %s
                       ORDER BY importance DESC, created_at DESC LIMIT %s""",
                    (address.namespace, limit),
                )
            rows = cursor.fetchall()
        return [self._memory(row) for row in rows]

    def save_run(self, record: RunRecord, idempotency_key: str | None = None) -> RunRecord:
        record.updated_at = utc_now()
        payload = record.model_dump(mode="json")
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO harness_runs
                   (run_id, namespace, idempotency_key, record_json, status, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT(run_id) DO UPDATE SET
                     record_json=excluded.record_json,
                     status=excluded.status,
                     updated_at=excluded.updated_at""",
                (
                    record.run_id,
                    record.address.namespace,
                    idempotency_key,
                    json.dumps(payload, ensure_ascii=False),
                    record.status.value,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute("SELECT record_json FROM harness_runs WHERE run_id = %s", (run_id,))
            row = cursor.fetchone()
        return RunRecord.model_validate(row[0]) if row else None

    def get_idempotent_run(self, address: ContextAddress, key: str) -> RunRecord | None:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT record_json FROM harness_runs WHERE namespace = %s AND idempotency_key = %s",
                (address.namespace, key),
            )
            row = cursor.fetchone()
        return RunRecord.model_validate(row[0]) if row else None

    def list_pending_runs(self, tenant_id: str, limit: int) -> list[RunRecord]:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT record_json FROM harness_runs
                   WHERE status = 'waiting_approval'
                     AND record_json->'address'->>'tenant_id' = %s
                   ORDER BY updated_at ASC LIMIT %s""",
                (tenant_id, limit),
            )
            rows = cursor.fetchall()
        return [RunRecord.model_validate(row[0]) for row in rows]

    def expire_pending_runs(self, cutoff: datetime, *, dry_run: bool = True) -> int:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT run_id, record_json FROM harness_runs
                   WHERE status = %s AND updated_at < %s FOR UPDATE""",
                (RunStatus.waiting_approval.value, cutoff),
            )
            rows = cursor.fetchall()
            if not dry_run:
                for run_id, payload in rows:
                    record = RunRecord.model_validate(payload)
                    record.status = RunStatus.failed
                    record.error = ErrorDetail(
                        code="approval_expired",
                        message="the seven-day approval window expired",
                        stage="approval",
                    )
                    record.updated_at = utc_now()
                    cursor.execute(
                        """UPDATE harness_runs SET record_json = %s, status = %s, updated_at = %s
                           WHERE run_id = %s""",
                        (
                            json.dumps(record.model_dump(mode="json"), ensure_ascii=False),
                            record.status.value,
                            record.updated_at,
                            run_id,
                        ),
                    )
        return len(rows)

    def append_audit(self, event: dict[str, Any]) -> None:
        payload = {"timestamp": utc_now().isoformat(), **event}
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO audit_events (id, event_json, created_at) VALUES (%s, %s, %s)",
                (new_id("audit"), json.dumps(payload, ensure_ascii=False), utc_now()),
            )

    def ready(self) -> bool:
        try:
            with self._pool.connection() as connection, connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() is not None
        except Exception:
            return False

    def prune_retention(
        self,
        short_term_cutoff: datetime,
        long_term_cutoff: datetime,
        *,
        dry_run: bool = True,
    ) -> dict[str, int]:
        with self._pool.connection() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT record_json FROM harness_runs WHERE created_at < %s FOR UPDATE",
                (short_term_cutoff,),
            )
            payload_records = [
                record
                for row in cursor.fetchall()
                if run_payload_needs_scrub(record := RunRecord.model_validate(row[0]))
            ]
            cursor.execute("SELECT COUNT(*) FROM context_messages WHERE created_at < %s", (short_term_cutoff,))
            message_row = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM context_memories WHERE created_at < %s", (long_term_cutoff,))
            memory_row = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM harness_runs WHERE updated_at < %s", (long_term_cutoff,))
            run_row = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM audit_events WHERE created_at < %s", (long_term_cutoff,))
            audit_row = cursor.fetchone()
            if not dry_run:
                for record in payload_records:
                    scrubbed = scrub_run_payload(record)
                    cursor.execute(
                        "UPDATE harness_runs SET record_json = %s WHERE run_id = %s",
                        (json.dumps(scrubbed.model_dump(mode="json"), ensure_ascii=False), scrubbed.run_id),
                    )
                cursor.execute("DELETE FROM context_messages WHERE created_at < %s", (short_term_cutoff,))
                cursor.execute("DELETE FROM context_memories WHERE created_at < %s", (long_term_cutoff,))
                cursor.execute("DELETE FROM harness_runs WHERE updated_at < %s", (long_term_cutoff,))
                cursor.execute("DELETE FROM audit_events WHERE created_at < %s", (long_term_cutoff,))
                cursor.execute(
                    """DELETE FROM context_threads t
                       WHERE t.updated_at < %s
                         AND NOT EXISTS (SELECT 1 FROM context_messages m WHERE m.namespace = t.namespace)
                         AND NOT EXISTS (SELECT 1 FROM context_memories m WHERE m.namespace = t.namespace)""",
                    (long_term_cutoff,),
                )
        return {
            "messages": int(message_row[0] if message_row else 0),
            "run_payloads_scrubbed": len(payload_records),
            "memories": int(memory_row[0] if memory_row else 0),
            "runs": int(run_row[0] if run_row else 0),
            "audit_events": int(audit_row[0] if audit_row else 0),
        }

    @staticmethod
    def _message(row: dict[str, Any]) -> StoredMessage:
        return StoredMessage(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            run_id=row["run_id"],
            metadata=row["metadata_json"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _memory(row: dict[str, Any]) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            kind=row["kind"],
            content=row["content"],
            importance=row["importance"],
            metadata=row["metadata_json"],
            created_at=row["created_at"],
        )
