# Production adoption decisions

## Decided defaults

- [x] Support protected single-host, private-cloud VM and Kubernetes deployments.
- [x] Use self-hosted Keycloak/OIDC; map `sub`, tenant, department, realm roles and clearance from signed access tokens.
- [x] Use Redis 8 for seven-day short-term conversations and LangGraph checkpoints.
- [x] Use MySQL 8.4 for approved long-term memory and minimal run/audit evidence; scrub short-term run payloads after seven days and delete long-term records after 365 days.
- [x] Prohibit data egress; allow only explicitly listed self-hosted OpenAI-compatible gateways.
- [x] Require `security_approver` review for confidential or secret runs.
- [x] Enforce four-eyes approval: the reviewer must be a different user in the same tenant.
- [x] Serialize cross-replica approval resume with expiring Redis run leases.

## Installation acceptance work

- [ ] Measure expected concurrency, peak request rate, P95 latency and maximum approval backlog.
- [ ] Build release-blocking evaluation datasets and thresholds for all six agents.
- [ ] Select the actual on-premises models and test the primary/fallback quality and capacity.
- [ ] Integrate the target secret manager and internal image registry.
- [ ] Define backup location, legal-hold exceptions and tenant deletion/export procedures.
- [ ] Decide whether the workload needs a durable external run queue beyond the bounded in-process pool.
- [ ] Run load, restore, penetration, prompt-injection and cross-tenant isolation tests.
