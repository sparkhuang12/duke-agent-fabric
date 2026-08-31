# API reference

The current API prefix is `/api/v1`. Development OpenAPI is available at `/docs`.

## Identity

Production endpoints require an OIDC access token:

```http
Authorization: Bearer eyJ...
```

The token must contain the configured issuer, audience, `sub`, tenant, department, roles and clearance claims. Development mode can use these test-only headers:

```http
X-Duke-Tenant: tenant-a
X-Duke-User: alice
X-Duke-Roles: user,approver
X-Duke-Department: office
X-Duke-Clearance: internal
```

Production ignores the `X-Duke-*` identity headers. The JWT signature and claims are validated locally using the allow-listed JWKS endpoint.

## Create a run

```http
POST /api/v1/runs
Content-Type: application/json

{
  "agent_id": "meeting",
  "thread_id": "weekly-sync-2026-08-31",
  "input": "Create minutes from the supplied transcript.",
  "idempotency_key": "client-request-42",
  "security_level": "internal",
  "memory_scope": "short_term",
  "metadata": {"source": "portal"}
}
```

The response is a `RunRecord`. Typical statuses are:

- `completed`: output is authorized and persisted;
- `waiting_approval`: a LangGraph interrupt is waiting for a human decision;
- `denied`: OPA, budget or manual review rejected the operation;
- `failed`: the run ended with structured error details.

## Resolve approval

```http
POST /api/v1/runs/{run_id}/approval
Content-Type: application/json

{
  "approved": true,
  "comment": "Sources and wording verified"
}
```

Ordinary review requires a different same-tenant user with the `approver` or `security_approver` role. `confidential` and `secret` runs require a different `security_approver`. The decision is checked by OPA.

Pending reviewers can query:

```text
GET /api/v1/approvals?limit=50
```

Redis checkpoints expire after seven days. A late approval becomes `approval_expired` rather than re-running the model.
Short-term run input/output and user-supplied metadata are scrubbed on the same seven-day schedule, so older `RunRecord` responses may contain empty payload fields while retaining status and audit identifiers.

## Inspect context

```http
GET /api/v1/contexts/{agent_id}/{thread_id}?q=search+terms
```

Context inspection is OPA-authorized and cannot select a different tenant or user through path parameters. The response contains the bounded summary, recent messages, matching private memories and truncation metadata.

## Operations and catalogs

```text
GET /api/v1/health/live
GET /api/v1/health/ready
GET /api/v1/agents
GET /api/v1/runs/{run_id}
GET /api/v1/tools
GET /api/v1/skills
GET /api/v1/model/status
GET /api/v1/policy/status
GET /metrics
```

Status endpoints never return API keys, full model credentials or raw policy input.

## Structured errors

```json
{
  "error": {
    "code": "model_unavailable",
    "message": "all configured models failed",
    "retryable": true,
    "stage": "model"
  }
}
```

Clients should use `code` and `retryable`, not parse `message`.

## Legacy compatibility

The original `/api/*` prototype routes remain enabled in development so the existing browser UI continues to work. They are disabled in the production Compose profile with `DUKE_EXPOSE_LEGACY_API=false` and should not be used by new clients.
