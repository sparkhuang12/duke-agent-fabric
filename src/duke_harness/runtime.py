from __future__ import annotations

from duke_harness.agents.registry import AgentRegistry
from duke_harness.config import Settings
from duke_harness.context.manager import ContextManager
from duke_harness.context.repository import repository_from_url
from duke_harness.harness.checkpoints import create_checkpointer
from duke_harness.harness.graph import HarnessGraphBuilder
from duke_harness.harness.runner import HarnessRunner
from duke_harness.identity.oidc import OIDCAuthenticator
from duke_harness.models.router import ModelRouter
from duke_harness.policy.client import PolicyClient
from duke_harness.resilience.run_locks import RunLockManager
from duke_harness.resilience.work_pool import BoundedWorkPool
from duke_harness.skills.loader import SkillRegistry
from duke_harness.tools.office import ToolRegistry


class Runtime:
    def __init__(self, settings: Settings, *, models: ModelRouter | None = None):
        self.settings = settings
        self.identity = OIDCAuthenticator(settings) if settings.auth_mode == "oidc" else None
        self.repository = repository_from_url(
            settings.database_url,
            settings.data_dir,
            redis_url=settings.redis_connection_url,
            short_term_ttl_seconds=settings.short_term_ttl_seconds,
        )
        self.agents = AgentRegistry(settings.agent_config_path)
        self.skills = SkillRegistry(settings.skills_manifest_path)
        self.tools = ToolRegistry()
        self.policies = PolicyClient(
            base_url=settings.opa_url,
            decision_path=settings.opa_decision_path,
            timeout_seconds=settings.opa_timeout_seconds,
            failure_mode=settings.opa_failure_mode,
            embedded_development_fallback=settings.opa_embedded_development_fallback,
        )
        self.models = models or ModelRouter(settings)
        self.run_locks = RunLockManager(settings.redis_connection_url)
        self.work_pool = BoundedWorkPool(
            workers=settings.execution_workers,
            max_pending=settings.max_pending_runs,
        )
        self.contexts = ContextManager(
            self.repository,
            recent_messages=settings.context_recent_messages,
            max_chars=settings.context_max_chars,
            summary_chars=settings.context_summary_chars,
        )
        self.checkpoints = create_checkpointer(
            settings.redis_connection_url,
            production=settings.is_production,
            ttl_minutes=settings.short_term_ttl_minutes,
        )
        self.graph = HarnessGraphBuilder(
            contexts=self.contexts,
            policies=self.policies,
            models=self.models,
            tools=self.tools,
            skills=self.skills,
            max_tool_calls=settings.max_tool_calls,
        ).build(self.checkpoints.saver)
        self.runner = HarnessRunner(
            graph=self.graph,
            repository=self.repository,
            agents=self.agents,
            policies=self.policies,
            max_run_seconds=settings.max_run_seconds,
            max_graph_steps=settings.max_graph_steps,
            approval_ttl_seconds=settings.short_term_ttl_seconds,
            run_locks=self.run_locks,
        )

    def close(self) -> None:
        self.work_pool.close()
        self.policies.close()
        if self.identity is not None:
            self.identity.close()
        self.models.close()
        self.run_locks.close()
        self.checkpoints.close()
        close = getattr(self.repository, "close", None)
        if close:
            close()
