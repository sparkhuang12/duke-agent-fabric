from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from duke_harness.context.models import MemoryItem, StoredMessage
from duke_harness.domain import ContextAddress, ErrorDetail, RunRecord, RunStatus, new_id, utc_now


class ContextRepository(ABC):
    @abstractmethod
    def append_message(
        self,
        address: ContextAddress,
        *,
        role: str,
        content: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> StoredMessage: ...

    @abstractmethod
    def recent_messages(self, address: ContextAddress, limit: int) -> list[StoredMessage]: ...

    @abstractmethod
    def message_count(self, address: ContextAddress) -> int: ...

    @abstractmethod
    def get_summary(self, address: ContextAddress) -> str: ...

    @abstractmethod
    def set_summary(self, address: ContextAddress, summary: str) -> None: ...

    @abstractmethod
    def add_memory(
        self,
        address: ContextAddress,
        *,
        content: str,
        kind: str = "episodic",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem: ...

    @abstractmethod
    def search_memories(self, address: ContextAddress, query: str, limit: int) -> list[MemoryItem]: ...

    @abstractmethod
    def save_run(self, record: RunRecord, idempotency_key: str | None = None) -> RunRecord: ...

    @abstractmethod
    def get_run(self, run_id: str) -> RunRecord | None: ...

    @abstractmethod
    def get_idempotent_run(self, address: ContextAddress, key: str) -> RunRecord | None: ...

    @abstractmethod
    def list_pending_runs(self, tenant_id: str, limit: int) -> list[RunRecord]: ...

    @abstractmethod
    def expire_pending_runs(self, cutoff: datetime, *, dry_run: bool = True) -> int: ...

    @abstractmethod
    def append_audit(self, event: dict[str, Any]) -> None: ...

    @abstractmethod
    def ready(self) -> bool: ...

    @abstractmethod
    def prune_retention(
        self,
        short_term_cutoff: datetime,
        long_term_cutoff: datetime,
        *,
        dry_run: bool = True,
    ) -> dict[str, int]: ...


def run_payload_needs_scrub(record: RunRecord) -> bool:
    """Return whether a non-approved-long-term run still contains short-lived content."""
    if record.memory_scope == "long_term" and record.status == RunStatus.completed:
        return False
    retention = record.metadata.get("retention")
    already_scrubbed = isinstance(retention, dict) and bool(retention.get("payload_scrubbed_at"))
    return not already_scrubbed or bool(record.input or record.output)


def scrub_run_payload(record: RunRecord) -> RunRecord:
    """Remove user-controlled content while retaining evidence needed for audit and support."""
    approval = record.metadata.get("approval")
    safe_metadata: dict[str, Any] = {
        "retention": {"payload_scrubbed_at": utc_now().isoformat()},
    }
    if isinstance(approval, dict):
        safe_metadata["approval"] = {
            "reviewer_id": str(approval.get("reviewer_id", "")),
            "roles": [str(role) for role in approval.get("roles", []) if isinstance(role, str)],
        }
    record.input = ""
    record.output = ""
    record.metadata = safe_metadata
    if record.error is not None:
        record.error.message = "error details removed by the short-term retention policy"
        record.error.details = {}
    return record


class SQLiteContextRepository(ContextRepository):
    """Single-file development store. Production uses Redis + MySQL."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS context_threads (
          namespace TEXT PRIMARY KEY,
          tenant_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          agent_id TEXT NOT NULL,
          thread_id TEXT NOT NULL,
          summary TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL,
          UNIQUE (tenant_id, user_id, agent_id, thread_id)
        );
        CREATE TABLE IF NOT EXISTS context_messages (
          id TEXT PRIMARY KEY,
          namespace TEXT NOT NULL REFERENCES context_threads(namespace) ON DELETE CASCADE,
          role TEXT NOT NULL,
          content TEXT NOT NULL,
          run_id TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
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
          importance REAL NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_memories_namespace
          ON context_memories(namespace, importance DESC, created_at DESC);
        CREATE TABLE IF NOT EXISTS harness_runs (
          run_id TEXT PRIMARY KEY,
          namespace TEXT NOT NULL,
          idempotency_key TEXT,
          record_json TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(namespace, idempotency_key)
        );
        CREATE INDEX IF NOT EXISTS idx_runs_status_updated ON harness_runs(status, updated_at DESC);
        CREATE TABLE IF NOT EXISTS audit_events (
          id TEXT PRIMARY KEY,
          event_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
        with self._lock, self._connect() as connection:
            connection.executescript(schema)

    @staticmethod
    def _thread_values(address: ContextAddress) -> tuple[str, str, str, str, str, str]:
        return (
            address.namespace,
            address.tenant_id,
            address.user_id,
            address.agent_id,
            address.thread_id,
            utc_now().isoformat(),
        )

    def _ensure_thread(self, connection: sqlite3.Connection, address: ContextAddress) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO context_threads
               (namespace, tenant_id, user_id, agent_id, thread_id, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            self._thread_values(address),
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
        with self._lock, self._connect() as connection:
            self._ensure_thread(connection, address)
            connection.execute(
                """INSERT OR IGNORE INTO context_messages
                   (id, namespace, role, content, run_id, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    message.id,
                    address.namespace,
                    message.role,
                    message.content,
                    message.run_id,
                    json.dumps(message.metadata, ensure_ascii=False),
                    message.created_at.isoformat(),
                ),
            )
        return message

    def recent_messages(self, address: ContextAddress, limit: int) -> list[StoredMessage]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT * FROM context_messages WHERE namespace = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (address.namespace, limit),
            ).fetchall()
        return [self._message_from_row(row) for row in reversed(rows)]

    def message_count(self, address: ContextAddress) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM context_messages WHERE namespace = ?", (address.namespace,)
            ).fetchone()
        return int(row["count"] if row else 0)

    def get_summary(self, address: ContextAddress) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT summary FROM context_threads WHERE namespace = ?", (address.namespace,)
            ).fetchone()
        return str(row["summary"]) if row else ""

    def set_summary(self, address: ContextAddress, summary: str) -> None:
        with self._lock, self._connect() as connection:
            self._ensure_thread(connection, address)
            connection.execute(
                "UPDATE context_threads SET summary = ?, updated_at = ? WHERE namespace = ?",
                (summary, utc_now().isoformat(), address.namespace),
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
        with self._lock, self._connect() as connection:
            self._ensure_thread(connection, address)
            connection.execute(
                """INSERT INTO context_memories
                   (id, namespace, kind, content, importance, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.id,
                    address.namespace,
                    item.kind,
                    item.content,
                    item.importance,
                    json.dumps(item.metadata, ensure_ascii=False),
                    item.created_at.isoformat(),
                ),
            )
        return item

    def search_memories(self, address: ContextAddress, query: str, limit: int) -> list[MemoryItem]:
        tokens = [token for token in query.strip().split() if token][:8]
        clauses = ["content LIKE ?" for _ in tokens]
        where = " AND (" + " OR ".join(clauses) + ")" if clauses else ""
        params: list[Any] = [address.namespace, *[f"%{token}%" for token in tokens], limit]
        with self._connect() as connection:
            rows = connection.execute(
                f"""SELECT * FROM context_memories WHERE namespace = ?{where}
                    ORDER BY importance DESC, created_at DESC LIMIT ?""",  # noqa: S608 - only generated clauses
                params,
            ).fetchall()
        return [self._memory_from_row(row) for row in rows]

    def save_run(self, record: RunRecord, idempotency_key: str | None = None) -> RunRecord:
        record.updated_at = utc_now()
        with self._lock, self._connect() as connection:
            connection.execute(
                """INSERT OR IGNORE INTO harness_runs
                   (run_id, namespace, idempotency_key, record_json, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.run_id,
                    record.address.namespace,
                    idempotency_key,
                    record.model_dump_json(),
                    record.status.value,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )
            row = connection.execute(
                "SELECT record_json FROM harness_runs WHERE run_id = ?", (record.run_id,)
            ).fetchone()
            if row is not None:
                connection.execute(
                    """UPDATE harness_runs SET record_json = ?, status = ?, updated_at = ?
                       WHERE run_id = ?""",
                    (record.model_dump_json(), record.status.value, record.updated_at.isoformat(), record.run_id),
                )
                return record
            if idempotency_key:
                row = connection.execute(
                    "SELECT record_json FROM harness_runs WHERE namespace = ? AND idempotency_key = ?",
                    (record.address.namespace, idempotency_key),
                ).fetchone()
                if row is not None:
                    return RunRecord.model_validate_json(row["record_json"])
        return record

    def get_run(self, run_id: str) -> RunRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT record_json FROM harness_runs WHERE run_id = ?", (run_id,)).fetchone()
        return RunRecord.model_validate_json(row["record_json"]) if row else None

    def get_idempotent_run(self, address: ContextAddress, key: str) -> RunRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM harness_runs WHERE namespace = ? AND idempotency_key = ?",
                (address.namespace, key),
            ).fetchone()
        return RunRecord.model_validate_json(row["record_json"]) if row else None

    def list_pending_runs(self, tenant_id: str, limit: int) -> list[RunRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT record_json FROM harness_runs WHERE status = ?
                   ORDER BY updated_at ASC LIMIT ?""",
                ("waiting_approval", limit * 4),
            ).fetchall()
        records = [RunRecord.model_validate_json(row["record_json"]) for row in rows]
        return [record for record in records if record.address.tenant_id == tenant_id][:limit]

    def expire_pending_runs(self, cutoff: datetime, *, dry_run: bool = True) -> int:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """SELECT run_id, record_json FROM harness_runs
                   WHERE status = ? AND updated_at < ?""",
                (RunStatus.waiting_approval.value, cutoff.isoformat()),
            ).fetchall()
            if not dry_run:
                for row in rows:
                    record = RunRecord.model_validate_json(row["record_json"])
                    record.status = RunStatus.failed
                    record.error = ErrorDetail(
                        code="approval_expired",
                        message="the seven-day approval window expired",
                        stage="approval",
                    )
                    record.updated_at = utc_now()
                    connection.execute(
                        """UPDATE harness_runs SET record_json = ?, status = ?, updated_at = ?
                           WHERE run_id = ?""",
                        (
                            record.model_dump_json(),
                            record.status.value,
                            record.updated_at.isoformat(),
                            record.run_id,
                        ),
                    )
        return len(rows)

    def append_audit(self, event: dict[str, Any]) -> None:
        payload = {"timestamp": utc_now().isoformat(), **event}
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO audit_events (id, event_json, created_at) VALUES (?, ?, ?)",
                (new_id("audit"), json.dumps(payload, ensure_ascii=False), payload["timestamp"]),
            )

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                return connection.execute("SELECT 1").fetchone() is not None
        except sqlite3.Error:
            return False

    def prune_retention(
        self,
        short_term_cutoff: datetime,
        long_term_cutoff: datetime,
        *,
        dry_run: bool = True,
    ) -> dict[str, int]:
        short_cutoff_text = short_term_cutoff.isoformat()
        long_cutoff_text = long_term_cutoff.isoformat()
        with self._lock, self._connect() as connection:
            payload_rows = connection.execute(
                "SELECT run_id, record_json FROM harness_runs WHERE created_at < ?",
                (short_cutoff_text,),
            ).fetchall()
            payload_records = [
                RunRecord.model_validate_json(row["record_json"])
                for row in payload_rows
                if run_payload_needs_scrub(RunRecord.model_validate_json(row["record_json"]))
            ]
            message_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM context_messages WHERE created_at < ?", (short_cutoff_text,)
                ).fetchone()[0]
            )
            memory_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM context_memories WHERE created_at < ?", (long_cutoff_text,)
                ).fetchone()[0]
            )
            run_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM harness_runs WHERE updated_at < ?", (long_cutoff_text,)
                ).fetchone()[0]
            )
            audit_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE created_at < ?", (long_cutoff_text,)
                ).fetchone()[0]
            )
            if not dry_run:
                for record in payload_records:
                    scrubbed = scrub_run_payload(record)
                    connection.execute(
                        "UPDATE harness_runs SET record_json = ? WHERE run_id = ?",
                        (scrubbed.model_dump_json(), scrubbed.run_id),
                    )
                connection.execute("DELETE FROM context_messages WHERE created_at < ?", (short_cutoff_text,))
                connection.execute("DELETE FROM context_memories WHERE created_at < ?", (long_cutoff_text,))
                connection.execute("DELETE FROM harness_runs WHERE updated_at < ?", (long_cutoff_text,))
                connection.execute("DELETE FROM audit_events WHERE created_at < ?", (long_cutoff_text,))
                connection.execute(
                    """DELETE FROM context_threads
                       WHERE updated_at < ?
                         AND NOT EXISTS (
                           SELECT 1 FROM context_messages m WHERE m.namespace = context_threads.namespace
                         )
                         AND NOT EXISTS (
                           SELECT 1 FROM context_memories m WHERE m.namespace = context_threads.namespace
                         )""",
                    (long_cutoff_text,),
                )
        return {
            "messages": message_count,
            "run_payloads_scrubbed": len(payload_records),
            "memories": memory_count,
            "runs": run_count,
            "audit_events": audit_count,
        }

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> StoredMessage:
        return StoredMessage(
            id=row["id"],
            role=row["role"],
            content=row["content"],
            run_id=row["run_id"],
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _memory_from_row(row: sqlite3.Row) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            kind=row["kind"],
            content=row["content"],
            importance=row["importance"],
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


def repository_from_url(
    database_url: str,
    data_dir: Path,
    *,
    redis_url: str = "",
    short_term_ttl_seconds: int = 7 * 24 * 60 * 60,
) -> ContextRepository:
    if database_url.startswith("sqlite:///"):
        configured = Path(database_url.removeprefix("sqlite:///"))
        path = configured if configured.is_absolute() else data_dir.parent / configured
        return SQLiteContextRepository(path.resolve())
    if database_url.startswith(("postgresql://", "postgres://")):
        from duke_harness.context.repository_postgres import PostgresContextRepository

        return PostgresContextRepository(database_url)
    if database_url.startswith(("mysql+pymysql://", "mysql://")):
        if not redis_url:
            raise ValueError("DUKE_REDIS_URL is required with MySQL")
        from duke_harness.context.repository_hybrid import HybridContextRepository
        from duke_harness.context.repository_mysql import MySQLLongTermRepository
        from duke_harness.context.repository_redis import RedisShortTermRepository

        return HybridContextRepository(
            short_term=RedisShortTermRepository(redis_url, ttl_seconds=short_term_ttl_seconds),
            long_term=MySQLLongTermRepository(database_url),
        )
    raise ValueError("DUKE_DATABASE_URL must use sqlite:///, mysql+pymysql:// or postgresql://")
