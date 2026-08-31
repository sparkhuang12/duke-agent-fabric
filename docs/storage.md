# Context storage and retention

## Short-term: Redis 8

Redis stores conversation turns, rolling summaries and LangGraph checkpoints. Each message older than seven days is removed even when its thread remains active; inactive thread keys expire natively. Checkpoint TTL is seven days with refresh-on-read disabled, so a pending approval cannot be extended merely by polling it.

Use Redis 8 because the LangGraph checkpointer requires RedisJSON and RediSearch. Configure authentication, TLS across hosts, `noeviction`, persistence/replication matching the approval SLO and alerts for memory pressure. Redis snapshots/AOF backups must not retain recoverable short-term content beyond the approved backup lifecycle.

## Long-term: MySQL 8.4

Only a request with `memory_scope=long_term` can promote the approved interaction into long-term memory. OPA always adds an approval obligation for that write. MySQL also stores run records and content-minimized audit events. For ordinary short-term runs, the maintenance command removes input, output, user metadata, approval comments and error details after seven days while retaining a minimal audit skeleton. A requested long-term run receives the one-year content window only after it completes approval; denied, failed and abandoned requests are scrubbed after seven days. Long-term memories, eligible run records and minimal audits are deleted after 365 days.

Use encrypted storage, TLS, least-privilege credentials, point-in-time recovery and restore drills. Binlog, replicas and backups must follow the same deletion/legal-hold policy; deleting a primary table alone is not complete erasure.

The idempotent bootstrap is [deploy/mysql/001-schema.sql](../deploy/mysql/001-schema.sql). Compose runs it only for a fresh data volume. VM/Kubernetes operators should apply it with a separate migration identity, then grant the application only runtime DML privileges; migration credentials must not be present in the API deployment.

## Isolation

Both tiers use the SHA-256 namespace derived from `tenant_id + user_id + agent_id + thread_id`. Short-term retrieval additionally filters each item against the caller's current clearance, so a later clearance downgrade cannot read previously authorized confidential context. Cross-agent sharing must use an explicit OPA-authorized knowledge resource.
