from __future__ import annotations

import json
from pathlib import Path

from duke_harness.domain import AgentSpec


class AgentRegistryError(RuntimeError):
    pass


class AgentRegistry:
    def __init__(self, path: Path):
        self._path = path
        self._agents = self._load(path)

    @staticmethod
    def _load(path: Path) -> dict[str, AgentSpec]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise AgentRegistryError(f"agent configuration not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise AgentRegistryError(f"invalid agent configuration: {path}") from exc
        agents = [AgentSpec.model_validate(item) for item in payload.get("agents", [])]
        registry = {agent.id: agent for agent in agents}
        if len(registry) != len(agents):
            raise AgentRegistryError("agent ids must be unique")
        if not registry:
            raise AgentRegistryError("at least one agent is required")
        return registry

    def get(self, agent_id: str) -> AgentSpec | None:
        return self._agents.get(agent_id)

    def require(self, agent_id: str) -> AgentSpec:
        agent = self.get(agent_id)
        if agent is None:
            raise AgentRegistryError(f"unknown agent: {agent_id}")
        return agent

    def list(self) -> list[AgentSpec]:
        return list(self._agents.values())
