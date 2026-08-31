from __future__ import annotations

import httpx
from conftest import ScriptedChatModel
from langchain_core.messages import AIMessage

from duke_harness.api.app import create_app
from duke_harness.models.router import ModelRouter
from duke_harness.runtime import Runtime

HEADERS = {"X-Duke-Tenant": "tenant", "X-Duke-User": "alice", "X-Duke-Roles": "user"}


async def test_api_requires_identity_and_runs_agent(settings) -> None:
    def factory(config):
        model = ScriptedChatModel([AIMessage(content="API output")])
        return Runtime(config, models=ModelRouter(config, models={"fake": model}, sleep=lambda _: None))

    app = create_app(settings, runtime_factory=factory)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get("/api/v1/agents")).status_code == 401
            response = await client.post(
                "/api/v1/runs",
                headers=HEADERS,
                json={"agent_id": "search", "thread_id": "api-thread", "input": "hello"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "completed"
            context = await client.get("/api/v1/contexts/search/api-thread", headers=HEADERS)
            assert context.status_code == 200
            assert len(context.json()["recent_messages"]) == 2
            assert (await client.get("/api/v1/skills", headers=HEADERS)).status_code == 200
            assert (await client.get("/metrics")).status_code == 200


async def test_legacy_model_placeholder_remains_compatible(settings) -> None:
    settings.model_name = ""
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/agents/document/run", json={"prompt": "test"})
            assert response.status_code == 200
            assert response.json()["model"]["status"] == "model_api_not_configured"


async def test_approver_sees_only_authorized_pending_queue(settings) -> None:
    def factory(config):
        model = ScriptedChatModel([AIMessage(content="draft")])
        return Runtime(config, models=ModelRouter(config, models={"fake": model}, sleep=lambda _: None))

    app = create_app(settings, runtime_factory=factory)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/runs",
                headers=HEADERS,
                json={"agent_id": "document", "thread_id": "pending", "input": "draft"},
            )
            assert created.json()["status"] == "waiting_approval"
            queue = await client.get(
                "/api/v1/approvals",
                headers={**HEADERS, "X-Duke-User": "reviewer", "X-Duke-Roles": "approver"},
            )
            assert [item["run_id"] for item in queue.json()["items"]] == [created.json()["run_id"]]
