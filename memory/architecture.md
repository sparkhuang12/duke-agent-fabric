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
- Type-check all optional storage drivers in CI, using the same Python target as the interpreter that installed their dependencies.
- The supported deployment profiles are protected single host, private-cloud VM and Kubernetes.

## Writing workbench

- `prototype/index.html` is the v1 writing desk. `prototype/operations.html` hosts the development dashboard. The homepage forwards legacy hash links; the optional legacy router is not a dependency of the writing desk.
- `config/agents.json` owns role descriptions, deliverables and review boundaries used by the desk and model. Each manuscript/role has its own thread. A structured document brief is submitted anew each round and classified together with the instruction.
- Approved turns form the revision history. The prompt budget prioritizes the latest draft and instruction before older excerpts. Historical excerpts and retrieved memories are model input data. Reviewers use the existing four-eyes approval endpoints.
- The browser keeps only manuscript references and development identity in tab-scoped storage. It rehydrates submitted briefs and versions through authorized run reads. Unsubmitted form edits live in page memory.

## Production assumptions still requiring owner decisions

- Expected concurrency, latency SLO and durable workload queue requirements.
- Tenant deletion/export, backup location and legal-hold exceptions.
- Actual on-premises model inventory and fallback order.
- Evaluation datasets and release-blocking quality thresholds for each agent.
- Organizational approver assignment, notifications and escalation timers.
