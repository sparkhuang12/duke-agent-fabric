USE duke;

CREATE TABLE IF NOT EXISTS duke_schema_migrations (
    version VARCHAR(32) PRIMARY KEY,
    applied_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS context_threads (
    namespace CHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(128) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    agent_id VARCHAR(128) NOT NULL,
    thread_id VARCHAR(128) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    UNIQUE KEY ux_context_address (tenant_id, user_id, agent_id, thread_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS context_memories (
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS harness_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    namespace CHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NULL,
    record_json JSON NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    UNIQUE KEY ux_runs_idempotency (namespace, idempotency_key),
    KEY idx_runs_status_updated (status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(64) PRIMARY KEY,
    event_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    KEY idx_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT IGNORE INTO duke_schema_migrations (version) VALUES ('0.3.0');
