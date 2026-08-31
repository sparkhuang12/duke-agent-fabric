# Production checklist

Before exposing the service to real users:

- Put the API behind an internal TLS ingress and pass the OIDC bearer token unchanged; development identity headers are disabled in production.
- Store the model API key, MySQL URL and Redis URL in a secret manager, not `.env` or Compose files.
- Use MySQL 8.4 with encrypted disks, point-in-time recovery and tested restore procedures.
- Use Redis 8 with authentication, TLS where it crosses hosts, persistence/replication appropriate to the seven-day approval SLO, and memory eviction disabled for checkpoint keys.
- Configure Keycloak/OIDC with MFA for approval roles and directory-managed tenant, department and clearance claims.
- Restrict egress to OPA, MySQL, Redis, Keycloak JWKS and an allow-listed on-premises model gateway.
- Distribute signed OPA bundles and export OPA decision logs to the audit platform.
- Set egress network policy so only the approved model gateway is reachable.
- Disable the legacy API and embedded policy fallback.
- Enforce seven-day short-term payload scrubbing and 365-day approved long-term retention; define deletion, legal hold and export exceptions.
- Verify backups, replicas, binlogs and log sinks cannot restore short-term content beyond the approved seven-day lifecycle.
- Schedule `duke-maintenance prune-context --apply` only after that retention policy is approved and tested.
- Add distributed rate limiting at the gateway and workload queues for sustained or bursty traffic.
- Export Prometheus metrics and JSON logs; define SLOs for run latency, model errors, OPA failures and approval backlog.
- Run prompt-injection, MCP supply-chain, cross-tenant isolation and disaster-recovery exercises.
- Build an evaluation set for every agent and block releases on quality, citation and policy regressions.
- Sign container images and generate an SBOM in CI.
