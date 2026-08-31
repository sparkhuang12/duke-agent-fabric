# Architecture

## Trust boundaries

Every run is addressed by four explicit identity dimensions:

```text
tenant_id / user_id / agent_id / thread_id
```

The tuple is hashed into an internal namespace. Database queries always use that namespace, LangGraph checkpoints use a separate run-specific hash, and agents never receive an API for selecting another namespace. Sharing across agents must be modeled as an explicit knowledge resource and authorized by OPA.

## Execution path

```text
OIDC Bearer JWT
        │
        ▼
FastAPI ingress ──► OPA input decision
        │
        ▼
Bounded context assembly
        │
        ▼
LangGraph model node ◄──────────────┐
        │                           │
        ├─ tool call ─► OPA ─► tool┘
        │
        ▼
OPA output decision
        │
        ├─ consequential output ─► durable human approval interrupt
        │
        ▼
Idempotent persistence + audit + metrics
```

## Context model

The context subsystem deliberately separates four kinds of state:

1. Request context: principal, deadline, run ID and request metadata. It is ephemeral.
2. Working state: LangGraph messages and node state. It is checkpointed for failure recovery and HITL resume.
3. Conversation context: recent user/assistant turns and a bounded rolling summary. It is scoped to one agent and thread.
4. Long-term memory: explicit facts, decisions or preferences. It is stored separately and retrieved only from the same namespace.

Checkpoints are not treated as a memory database. This allows checkpoint pruning without deleting user-visible conversation memory and allows memory retention rules without corrupting in-flight graphs.

## Failure model

Failures are classified into retryable provider failures, non-retryable validation/policy failures, tool failures and unhandled harness faults. Controls include:

- model timeout, bounded exponential retry and ordered model fallback;
- per-model circuit breakers;
- graph recursion, tool-call and wall-clock budgets;
- OPA fail-closed behavior in production;
- idempotency keys for run creation and unique run/role keys for final context writes;
- Redis per-run leases preventing concurrent resume across API replicas;
- seven-day LangGraph checkpoints and short-term conversation context in Redis 8;
- seven-day scrubbing of short-lived run payloads in MySQL, with only approved long-term content retained for one year;
- one-year deletion of long-term memories, run skeletons and content-minimized audits in MySQL 8.4;
- explicit waiting-for-approval state that survives API process restarts;
- structured error records and content-free audit events.

## Production gaps that belong outside this repository

The deployment environment must provide Keycloak-compatible OIDC, TLS termination, secret management, encrypted database volumes, backups, log shipping, alerting and network policy. The framework validates JWT signatures and claims locally against an allow-listed JWKS endpoint. Three deployment profiles are supplied, but their endpoints, secret integration, storage HA and private CIDRs must be adapted to the target environment.
