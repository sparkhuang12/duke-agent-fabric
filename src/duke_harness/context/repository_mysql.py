from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from duke_harness.context.models import MemoryItem
from duke_harness.context.repository import run_payload_needs_scrub, scrub_run_payload
from duke_harness.domain import ContextAddress, ErrorDetail, RunRecord, RunStatus, new_id, utc_now


def _mysql_datetime(value: datetime) -> datetime:
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _utc_datetime(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


class MySQLLongTermRepository:
    """One-year long-term memory, durable run metadata and content-free audit store."""

    def __init__(self, database_url: str):
        try:
            from sqlalchemy import create_engine
        except ImportError as exc:  # pragma: no cover - production optional dependency
            raise RuntimeError("install duke-agent-fabric[production] for MySQL support") from exc
        if database_url.startswith("mysql://"):
            database_url = "mysql+pymysql://" + database_url.removeprefix("mysql://")
        self._engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_size=10,
            max_overflow=10,
            connect_args={"charset": "utf8mb4", "connect_timeout": 5},
        )
        self._initialize()

    def _initialize(self) -> None:
        from sqlalchemy import text

        required_tables = {"context_threads", "context_memories", "harness_runs", "audit_events"}
        with self._engine.connect() as connection:
            existing_tables = set(
                connection.execute(
                    text(
                        """SELECT table_name FROM information_schema.tables
                           WHERE table_schema = DATABASE()
                             AND table_name IN ('context_threads', 'context_memories',
                                                'harness_runs', 'audit_events')"""
                    )
                ).scalars()
            )
        if required_tables.issubset(existing_tables):
            return

        statements = [
            """CREATE TABLE IF NOT EXISTS context_threads (
                namespace CHAR(64) PRIMARY KEY,
                tenant_id VARCHAR(128) NOT NULL,
                user_id VARCHAR(128) NOT NULL,
                agent_id VARCHAR(128) NOT NULL,
                thread_id VARCHAR(128) NOT NULL,
                updated_at DATETIME(6) NOT NULL,
                UNIQUE KEY ux_context_address (tenant_id, user_id, agent_id, thread_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""",
            """CREATE TABLE IF NOT EXISTS context_memories (
                id VARCHAR(64) PRIMARY KEY,
                namespace CHAR(64) NOT NULL,
                kind VARCHAR(32) NOT NULL,
                content LONGTEXT NOT NULL,
                importance DOUBLE NOT NULL,
                metadata_json JSON NOT NULL,
                created_at DATETIME(6) NOT NULL,
                KEY idx_memories_namespace (namespace, importance, created_at),
                CONSTRAINT fk_memories_thread FOREIGN KEY (namespace)
                    REFERENCES context_threads(namespace) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""",
            """CREATE TABLE IF NOT EXISTS harness_runs (
                run_id VARCHAR(64) PRIMARY KEY,
                namespace CHAR(64) NOT NULL,
                idempotency_key VARCHAR(128) NULL,
                record_json JSON NOT NULL,
                status VARCHAR(32) NOT NULL,
                created_at DATETIME(6) NOT NULL,
                updated_at DATETIME(6) NOT NULL,
                UNIQUE KEY ux_runs_idempotency (namespace, idempotency_key),
                KEY idx_runs_status_updated (status, updated_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""",
            """CREATE TABLE IF NOT EXISTS audit_events (
                id VARCHAR(64) PRIMARY KEY,
                event_json JSON NOT NULL,
                created_at DATETIME(6) NOT NULL,
                KEY idx_audit_created (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci""",
        ]
        with self._engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))

    @staticmethod
    def _ensure_thread(connection: Any, address: ContextAddress) -> None:
        from sqlalchemy import text

        connection.execute(
            text(
                """INSERT INTO context_threads
                   (namespace, tenant_id, user_id, agent_id, thread_id, updated_at)
                   VALUES (:namespace, :tenant_id, :user_id, :agent_id, :thread_id, :updated_at)
                   ON DUPLICATE KEY UPDATE updated_at = VALUES(updated_at)"""
            ),
            {
                "namespace": address.namespace,
                "tenant_id": address.tenant_id,
                "user_id": address.user_id,
                "agent_id": address.agent_id,
                "thread_id": address.thread_id,
                "updated_at": _mysql_datetime(utc_now()),
            },
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
        from sqlalchemy import text

        item = MemoryItem(
            id=new_id("mem"),
            kind=kind,  # type: ignore[arg-type]
            content=content,
            importance=importance,
            metadata=metadata or {},
            created_at=utc_now(),
        )
        with self._engine.begin() as connection:
            self._ensure_thread(connection, address)
            connection.execute(
                text(
                    """INSERT INTO context_memories
                       (id, namespace, kind, content, importance, metadata_json, created_at)
                       VALUES (:id, :namespace, :kind, :content, :importance, :metadata_json, :created_at)"""
                ),
                {
                    "id": item.id,
                    "namespace": address.namespace,
                    "kind": item.kind,
                    "content": item.content,
                    "importance": item.importance,
                    "metadata_json": json.dumps(item.metadata, ensure_ascii=False),
                    "created_at": _mysql_datetime(item.created_at),
                },
            )
        return item

    def search_memories(self, address: ContextAddress, query: str, limit: int) -> list[MemoryItem]:
        from sqlalchemy import text

        tokens = [token for token in query.strip().split() if token][:8]
        conditions = [f"content LIKE :token_{index}" for index in range(len(tokens))]
        where = " AND (" + " OR ".join(conditions) + ")" if conditions else ""
        params: dict[str, Any] = {"namespace": address.namespace, "limit": limit}
        params.update({f"token_{index}": f"%{token}%" for index, token in enumerate(tokens)})
        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""SELECT id, kind, content, importance, metadata_json, created_at
                        FROM context_memories WHERE namespace = :namespace{where}
                        ORDER BY importance DESC, created_at DESC LIMIT :limit"""  # noqa: S608
                ),
                params,
            ).mappings()
            return [
                MemoryItem(
                    id=row["id"],
                    kind=row["kind"],
                    content=row["content"],
                    importance=row["importance"],
                    metadata=_json_value(row["metadata_json"]),
                    created_at=_utc_datetime(row["created_at"]),
                )
                for row in rows
            ]

    def save_run(self, record: RunRecord, idempotency_key: str | None = None) -> RunRecord:
        from sqlalchemy import text

        record.updated_at = utc_now()
        with self._engine.begin() as connection:
            existing = connection.execute(
                text("SELECT record_json FROM harness_runs WHERE run_id = :run_id FOR UPDATE"),
                {"run_id": record.run_id},
            ).scalar_one_or_none()
            if existing is not None:
                connection.execute(
                    text(
                        """UPDATE harness_runs
                           SET record_json = :record_json, status = :status, updated_at = :updated_at
                           WHERE run_id = :run_id"""
                    ),
                    {
                        "record_json": record.model_dump_json(),
                        "status": record.status.value,
                        "updated_at": _mysql_datetime(record.updated_at),
                        "run_id": record.run_id,
                    },
                )
                return record
            if idempotency_key:
                idempotent = connection.execute(
                    text(
                        """SELECT record_json FROM harness_runs
                           WHERE namespace = :namespace AND idempotency_key = :idempotency_key FOR UPDATE"""
                    ),
                    {"namespace": record.address.namespace, "idempotency_key": idempotency_key},
                ).scalar_one_or_none()
                if idempotent is not None:
                    return RunRecord.model_validate(_json_value(idempotent))
            connection.execute(
                text(
                    """INSERT INTO harness_runs
                       (run_id, namespace, idempotency_key, record_json, status, created_at, updated_at)
                       VALUES (:run_id, :namespace, :idempotency_key, :record_json,
                               :status, :created_at, :updated_at)
                       ON DUPLICATE KEY UPDATE run_id = run_id"""
                ),
                {
                    "run_id": record.run_id,
                    "namespace": record.address.namespace,
                    "idempotency_key": idempotency_key,
                    "record_json": record.model_dump_json(),
                    "status": record.status.value,
                    "created_at": _mysql_datetime(record.created_at),
                    "updated_at": _mysql_datetime(record.updated_at),
                },
            )
            if idempotency_key:
                payload = connection.execute(
                    text(
                        """SELECT record_json FROM harness_runs
                           WHERE namespace = :namespace AND idempotency_key = :idempotency_key"""
                    ),
                    {"namespace": record.address.namespace, "idempotency_key": idempotency_key},
                ).scalar_one()
                stored = RunRecord.model_validate(_json_value(payload))
                if stored.run_id != record.run_id:
                    return stored
        return record

    def get_run(self, run_id: str) -> RunRecord | None:
        from sqlalchemy import text

        with self._engine.connect() as connection:
            payload = connection.execute(
                text("SELECT record_json FROM harness_runs WHERE run_id = :run_id"), {"run_id": run_id}
            ).scalar_one_or_none()
        return RunRecord.model_validate(_json_value(payload)) if payload is not None else None

    def get_idempotent_run(self, address: ContextAddress, key: str) -> RunRecord | None:
        from sqlalchemy import text

        with self._engine.connect() as connection:
            payload = connection.execute(
                text(
                    """SELECT record_json FROM harness_runs
                       WHERE namespace = :namespace AND idempotency_key = :idempotency_key"""
                ),
                {"namespace": address.namespace, "idempotency_key": key},
            ).scalar_one_or_none()
        return RunRecord.model_validate(_json_value(payload)) if payload is not None else None

    def list_pending_runs(self, tenant_id: str, limit: int) -> list[RunRecord]:
        from sqlalchemy import text

        with self._engine.connect() as connection:
            rows = connection.execute(
                text(
                    """SELECT record_json FROM harness_runs
                       WHERE status = 'waiting_approval'
                         AND JSON_UNQUOTE(JSON_EXTRACT(record_json, '$.address.tenant_id')) = :tenant_id
                       ORDER BY updated_at ASC LIMIT :limit"""
                ),
                {"tenant_id": tenant_id, "limit": limit},
            ).all()
        return [RunRecord.model_validate(_json_value(row[0])) for row in rows]

    def expire_pending_runs(self, cutoff: datetime, *, dry_run: bool = True) -> int:
        from sqlalchemy import text

        with self._engine.begin() as connection:
            rows = connection.execute(
                text(
                    """SELECT run_id, record_json FROM harness_runs
                       WHERE status = :status AND updated_at < :cutoff FOR UPDATE"""
                ),
                {"status": RunStatus.waiting_approval.value, "cutoff": _mysql_datetime(cutoff)},
            ).all()
            if not dry_run:
                for run_id, payload in rows:
                    record = RunRecord.model_validate(_json_value(payload))
                    record.status = RunStatus.failed
                    record.error = ErrorDetail(
                        code="approval_expired",
                        message="the seven-day approval window expired",
                        stage="approval",
                    )
                    record.updated_at = utc_now()
                    connection.execute(
                        text(
                            """UPDATE harness_runs SET record_json = :record_json,
                               status = :status, updated_at = :updated_at WHERE run_id = :run_id"""
                        ),
                        {
                            "record_json": record.model_dump_json(),
                            "status": record.status.value,
                            "updated_at": _mysql_datetime(record.updated_at),
                            "run_id": run_id,
                        },
                    )
        return len(rows)

    def append_audit(self, event: dict[str, Any]) -> None:
        from sqlalchemy import text

        payload = {"timestamp": utc_now().isoformat(), **event}
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    """INSERT INTO audit_events (id, event_json, created_at)
                       VALUES (:id, :event_json, :created_at)"""
                ),
                {
                    "id": new_id("audit"),
                    "event_json": json.dumps(payload, ensure_ascii=False),
                    "created_at": _mysql_datetime(utc_now()),
                },
            )

    def ready(self) -> bool:
        from sqlalchemy import text

        try:
            with self._engine.connect() as connection:
                return bool(connection.execute(text("SELECT 1")).scalar_one() == 1)
        except Exception:
            return False

    def prune_before(
        self,
        short_term_cutoff: datetime,
        long_term_cutoff: datetime,
        *,
        dry_run: bool = True,
    ) -> dict[str, int]:
        from sqlalchemy import text

        short_cutoff_value = _mysql_datetime(short_term_cutoff)
        long_cutoff_value = _mysql_datetime(long_term_cutoff)
        queries = {
            "memories": "SELECT COUNT(*) FROM context_memories WHERE created_at < :cutoff",
            "runs": "SELECT COUNT(*) FROM harness_runs WHERE updated_at < :cutoff",
            "audit_events": "SELECT COUNT(*) FROM audit_events WHERE created_at < :cutoff",
        }
        with self._engine.begin() as connection:
            payload_rows = connection.execute(
                text("SELECT record_json FROM harness_runs WHERE created_at < :cutoff FOR UPDATE"),
                {"cutoff": short_cutoff_value},
            ).scalars()
            payload_records = [
                record
                for payload in payload_rows
                if run_payload_needs_scrub(record := RunRecord.model_validate(_json_value(payload)))
            ]
            counts = {
                name: int(connection.execute(text(query), {"cutoff": long_cutoff_value}).scalar_one())
                for name, query in queries.items()
            }
            counts["run_payloads_scrubbed"] = len(payload_records)
            if not dry_run:
                for record in payload_records:
                    scrubbed = scrub_run_payload(record)
                    connection.execute(
                        text("UPDATE harness_runs SET record_json = :record_json WHERE run_id = :run_id"),
                        {"record_json": scrubbed.model_dump_json(), "run_id": scrubbed.run_id},
                    )
                connection.execute(
                    text("DELETE FROM context_memories WHERE created_at < :cutoff"), {"cutoff": long_cutoff_value}
                )
                connection.execute(
                    text("DELETE FROM harness_runs WHERE updated_at < :cutoff"), {"cutoff": long_cutoff_value}
                )
                connection.execute(
                    text("DELETE FROM audit_events WHERE created_at < :cutoff"), {"cutoff": long_cutoff_value}
                )
                connection.execute(
                    text(
                        """DELETE t FROM context_threads t
                           LEFT JOIN context_memories m ON m.namespace = t.namespace
                           WHERE t.updated_at < :cutoff AND m.id IS NULL"""
                    ),
                    {"cutoff": long_cutoff_value},
                )
        return counts

    def close(self) -> None:
        self._engine.dispose()
