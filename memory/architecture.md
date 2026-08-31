# Durable project memory

## Current direction

- The public project/distribution name is Duke Agent Fabric (`duke-agent-fabric`); the internal `duke_harness` Python namespace and legacy CLI alias remain for compatibility.
- The project is a policy-governed multi-agent harness, not only an office UI.
- Python, FastAPI, LangChain and LangGraph are the primary runtime stack.
- OPA is the enforceable policy engine and must fail closed in production.
- The model boundary is OpenAI-compatible and provider-neutral.
- Production short-term conversations and LangGraph checkpoints use Redis 8 with a fixed seven-day TTL.
- Production long-term memory, run skeletons and content-minimized audit events use MySQL 8.4; short-term run payloads are scrubbed after seven days and approved long-term content is deleted after 365 days. SQLite is local/test only.
- Context isolation key is `tenant_id + user_id + agent_id + thread_id`.
- LangGraph checkpoints, conversation messages and long-term memories are distinct stores/lifecycles.
- Agent-to-agent memory sharing is denied by construction. Shared knowledge must be an explicit OPA-authorized resource.
- MCP tools reuse policy-aware pure functions; local stdio identity is process-bound and cannot be elevated through tool arguments.
- Vendored skills are text-only, commit-pinned, checksum-verified and license-reviewed.
- All manual approvals enforce four-eyes separation; confidential and secret runs require a different same-tenant `security_approver`.
- Concurrent approval resume is serialized across replicas with an expiring Redis per-run lease.
- Production identity uses self-hosted Keycloak-compatible OIDC with locally validated JWTs and mapped tenant/department/role/clearance claims.
- Model traffic is restricted to explicitly allow-listed self-hosted OpenAI-compatible gateways; public SaaS and external tracing are forbidden by default.
- The supported deployment profiles are protected single host, private-cloud VM and Kubernetes.

## Production assumptions still requiring owner decisions

- Expected concurrency, latency SLO and durable workload queue requirements.
- Tenant deletion/export, backup location and legal-hold exceptions.
- Actual on-premises model inventory and fallback order.
- Evaluation datasets and release-blocking quality thresholds for each agent.
- Human approval UI, approver resolution and escalation timers.
