# Identity and approval model

Production uses OIDC access tokens and defaults to self-hosted Keycloak so identity data and token validation remain inside the approved network. The application validates signature, issuer, audience, expiry and signing algorithm locally; only the allow-listed JWKS endpoint is contacted, with ambient HTTP proxies disabled.

## Authoritative claims

| Duke field | Default token claim | Source of truth |
| --- | --- | --- |
| `user_id` | `sub` | Keycloak immutable user identifier |
| `tenant_id` | `tenant_id` | Organization/tenant directory attribute |
| `department` | `department` | HR/LDAP/SCIM-managed user attribute |
| `roles` | `realm_access.roles` | Keycloak realm role assignments |
| `clearance` | `clearance` | Security-office-managed attribute |

The supplied realm template configures the audience and custom-attribute Protocol Mappers. It intentionally contains no users or secrets. In production, provision attributes from the organization's authoritative directory and prevent ordinary users from editing them.

Supported clearances are `public < internal < confidential < secret`. OPA denies access above the caller's clearance. `confidential` and `secret` runs always require a `security_approver`; ordinary mandatory-review runs require `approver` or `security_approver`. The reviewer must be a different user in the same tenant.

## Approval queue

`GET /api/v1/approvals` returns only pending runs that the current token is authorized to approve. Approval checkpoints use the same seven-day Redis TTL as short-term context. An approval attempted after that window is marked `approval_expired`; it is never reconstructed from model output alone.

For production Keycloak, enable MFA for approval roles, short access-token lifetimes, brute-force detection, admin-event auditing and the latest patched release. Keep realm administration separate from application administration.
