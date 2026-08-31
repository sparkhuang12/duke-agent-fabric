from __future__ import annotations

from typing import Any

import httpx

from duke_harness.domain import AgentSpec, ContextAddress, PolicyDecision, Principal, new_id


class PolicyUnavailableError(RuntimeError):
    pass


class PolicyClient:
    def __init__(
        self,
        *,
        base_url: str,
        decision_path: str,
        timeout_seconds: float = 2.0,
        failure_mode: str = "closed",
        embedded_development_fallback: bool = False,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.decision_path = "/" + decision_path.lstrip("/")
        self.failure_mode = failure_mode
        self.embedded_development_fallback = embedded_development_fallback
        # OPA is a trusted sidecar/internal service. Never route policy traffic
        # through ambient HTTP proxy variables.
        self._client = httpx.Client(timeout=timeout_seconds, transport=transport, trust_env=False)

    def close(self) -> None:
        self._client.close()

    def decide(
        self,
        *,
        action: str,
        principal: Principal,
        address: ContextAddress,
        agent: AgentSpec,
        resource: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        policy_input = {
            "action": action,
            "subject": principal.model_dump(),
            "address": address.model_dump(),
            "agent": {
                "id": agent.id,
                "allowed_tools": agent.allowed_tools,
                "allowed_roles": agent.allowed_roles,
                "require_approval": agent.require_approval,
            },
            "resource": resource or {},
            "context": context or {},
        }
        try:
            response = self._client.post(
                f"{self.base_url}{self.decision_path}",
                json={"input": policy_input},
                headers={"X-Request-ID": new_id("policy")},
            )
            response.raise_for_status()
            payload = response.json()
            result = payload.get("result")
            if not isinstance(result, dict) or "allow" not in result:
                raise PolicyUnavailableError("OPA returned an undefined or malformed decision")
            return PolicyDecision(
                allow=bool(result["allow"]),
                reasons=[str(item) for item in result.get("reasons", [])],
                obligations=dict(result.get("obligations", {})),
                decision_id=str(payload.get("decision_id", "")),
                source="opa",
            )
        except (httpx.HTTPError, ValueError, PolicyUnavailableError) as exc:
            if self.embedded_development_fallback:
                return self._embedded_decision(policy_input, reason=f"OPA unavailable: {type(exc).__name__}")
            if self.failure_mode == "open":
                return PolicyDecision(
                    allow=True,
                    reasons=["OPA unavailable; allowed by configured fail-open mode"],
                    source="failure",
                )
            return PolicyDecision(
                allow=False,
                reasons=["OPA unavailable; denied by fail-closed policy"],
                source="failure",
            )

    def ready(self) -> bool:
        try:
            response = self._client.get(f"{self.base_url}/health?bundles=true", timeout=1.0)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    @staticmethod
    def _embedded_decision(policy_input: dict[str, Any], reason: str) -> PolicyDecision:
        subject = policy_input["subject"]
        address = policy_input["address"]
        agent = policy_input["agent"]
        resource = policy_input["resource"]
        action = policy_input["action"]
        reasons = [reason]
        allow = subject["tenant_id"] == address["tenant_id"] and subject["user_id"] == address["user_id"]
        if not allow:
            reasons.append("principal does not own the context namespace")
        if action == "tool.call" and resource.get("tool_name") not in agent.get("allowed_tools", []):
            allow = False
            reasons.append("tool is not allow-listed for this agent")
        if action != "run.approve" and not set(subject.get("roles", [])).intersection(agent.get("allowed_roles", [])):
            allow = False
            reasons.append("principal has no role allowed by this agent")
        ranks = {"public": 0, "internal": 1, "confidential": 2, "secret": 3}
        security_level = str(resource.get("security_level", "internal"))
        if ranks.get(str(subject.get("clearance", "internal")), 1) < ranks.get(security_level, 1):
            allow = False
            reasons.append("subject clearance is insufficient")
        if action == "run.approve":
            roles = set(subject.get("roles", []))
            required = "security_approver" if security_level in {"confidential", "secret"} else "approver"
            allow = (
                subject["tenant_id"] == address["tenant_id"]
                and subject["user_id"] != address["user_id"]
                and (required in roles or "security_approver" in roles)
            )
            if not allow:
                reasons.append(f"approval requires a different same-tenant reviewer with role {required}")
        manual_approval = bool(agent.get("require_approval"))
        manual_approval = manual_approval or security_level in {"confidential", "secret"}
        manual_approval = manual_approval or resource.get("memory_scope") == "long_term"
        return PolicyDecision(
            allow=allow,
            reasons=reasons,
            obligations={"manual_approval": manual_approval},
            decision_id=new_id("embedded"),
            source="embedded",
        )
