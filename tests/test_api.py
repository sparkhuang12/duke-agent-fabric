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
                json={"agent_id": "fiction", "thread_id": "api-thread", "input": "hello"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "completed"
            context = await client.get("/api/v1/contexts/fiction/api-thread", headers=HEADERS)
            assert context.status_code == 200
            assert len(context.json()["recent_messages"]) == 2
            assert (await client.get("/api/v1/skills", headers=HEADERS)).status_code == 404
            assert (await client.get("/metrics")).status_code == 200


async def test_approver_sees_only_authorized_pending_queue(settings) -> None:
    def factory(config):
        model = ScriptedChatModel([AIMessage(content="draft")])
        return Runtime(config, models=ModelRouter(config, models={"fake": model}, sleep=lambda _: None))

    app = create_app(settings, runtime_factory=factory)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # A pending run from a retired role can still exist after an upgrade.
            from duke_harness.domain import ContextAddress, RunRecord, RunStatus

            app.state.runtime.repository.save_run(
                RunRecord(
                    run_id="pre-upgrade",
                    address=ContextAddress(tenant_id="tenant", user_id="alice", agent_id="document", thread_id="old"),
                    status=RunStatus.waiting_approval,
                    input="old",
                )
            )
            created = await client.post(
                "/api/v1/runs",
                headers=HEADERS,
                json={"agent_id": "fiction", "thread_id": "pending", "input": "draft", "memory_scope": "long_term"},
            )
            assert created.json()["status"] == "waiting_approval"
            queue = await client.get(
                "/api/v1/approvals",
                headers={**HEADERS, "X-Duke-User": "reviewer", "X-Duke-Roles": "approver"},
            )
            assert [item["run_id"] for item in queue.json()["items"]] == [created.json()["run_id"]]


async def test_only_the_novel_editor_is_available(settings) -> None:
    def factory(config):
        model = ScriptedChatModel([AIMessage(content="信纸在灯下显出了第二行字。")])
        return Runtime(config, models=ModelRouter(config, models={"fake": model}))

    app = create_app(settings, runtime_factory=factory)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        session = (await client.get("/api/v1/workbench/session", headers=HEADERS)).json()
        assert session["fiction_available"]
        for path in ("/office.html", "/operations.html", "/api/agents", "/api/knowledge", "/api/v1/tools"):
            assert (await client.get(path, headers=HEADERS)).status_code == 404
        catalog = await client.get("/api/v1/agents", headers=HEADERS)
        assert [agent["id"] for agent in catalog.json()["items"]] == ["fiction"]
        removed = await client.post("/api/v1/runs", headers=HEADERS, json={"agent_id": "meeting", "input": "test"})
        assert removed.status_code == 404 and removed.json()["error"]["code"] == "unknown_agent"
        reviewer = {**HEADERS, "X-Duke-Roles": "approver"}
        assert not (await client.get("/api/v1/workbench/session", headers=reviewer)).json()["fiction_available"]
        result = await client.post(
            "/api/v1/runs",
            headers=HEADERS,
            json={"agent_id": "fiction", "thread_id": "novel-draft", "input": "续写收到来信的场景。"},
        )
        run = result.json()
        assert run["status"] == "completed" and "信纸" in run["output"]
        url = f"/api/v1/runs/{run['run_id']}"
        assert (await client.get(url, headers={**HEADERS, "X-Duke-User": "other"})).status_code in {403, 404}
