# Security policy

## Supported versions

Until the first stable release, only the latest release on the default branch receives security fixes.

## Reporting a vulnerability

Use GitHub Private Vulnerability Reporting for the repository. If it is not enabled yet, contact the repository owner privately and ask for a secure reporting channel; do not open a public issue.

Include the affected version, deployment mode, impact, minimum reproduction and suggested mitigation. Remove real credentials, personal data, prompts and documents. Reports involving cross-tenant access, OIDC bypass, OPA bypass, arbitrary tool execution, checkpoint deserialization, Skill/MCP supply-chain compromise or data egress are treated as high priority.

The maintainer should acknowledge a complete report within seven days, coordinate a fix and advisory, and avoid disclosing reporter details without permission. This is a best-effort open-source policy, not a commercial support SLA.

## Deployment boundary

This repository provides secure defaults, not a compliance certificate. Operators remain responsible for TLS, patched dependencies, secret management, internal image mirrors, Keycloak hardening, MySQL/Redis encryption and backups, network egress controls, model approval, monitoring and incident response.
