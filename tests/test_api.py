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


async def test_writing_desk_revises_only_the_approved_manuscript(settings) -> None:
    from langchain_core.messages import BaseMessage
    from pydantic import PrivateAttr

    class RecordingModel(ScriptedChatModel):
        _history: list[list[BaseMessage]] = PrivateAttr(default_factory=list)

        def _generate(self, messages, **kwargs):
            self._history.append(list(messages))
            return super()._generate(messages, **kwargs)

    model = RecordingModel(
        [AIMessage(content=text) for text in ("第一版完整正文", "第二版正文", "另一份稿", "其他角色")]
    )
    app = create_app(
        settings, runtime_factory=lambda cfg: Runtime(cfg, models=ModelRouter(cfg, models={"fake": model}))
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client,
    ):
        session = (await client.get("/api/v1/workbench/session", headers=HEADERS)).json()
        assert len(session["agents"]) == 6 and all(role["boundary"] for role in session["agents"])
        assert not session["can_review"] and session["model_configured"]
        brief = {"document_type": "通知", "audience": "各直属单位", "materials": "十二月报送清单"}
        payload = {"agent_id": "document", "thread_id": "draft-a", "input": "起草通知", "writing_brief": brief}
        first = (await client.post("/api/v1/runs", headers=HEADERS, json=payload)).json()
        assert first["status"] == "waiting_approval" and first["metadata"]["writing_brief"] == brief
        assert "十二月报送清单" in model._history[0][-1].content
        reviewer = {**HEADERS, "X-Duke-User": "reviewer", "X-Duke-Roles": "approver"}
        url = f"/api/v1/runs/{first['run_id']}/approval"
        assert (await client.post(url, headers=HEADERS, json={"approved": True})).status_code == 403
        assert (await client.post(url, headers=reviewer, json={"approved": True})).json()["status"] == "completed"
        assert (await client.post(url, headers=HEADERS, json={"approved": True})).status_code == 403
        await client.post("/api/v1/runs", headers=HEADERS, json={**payload, "input": "只压缩背景段"})
        assert "第一版完整正文" in [message.content for message in model._history[1]]
        assert "只压缩背景段" in model._history[1][-1].content
        await client.post("/api/v1/runs", headers=HEADERS, json={**payload, "thread_id": "draft-b"})
        await client.post(
            "/api/v1/runs",
            headers=HEADERS,
            json={"agent_id": "search", "thread_id": "draft-a", "input": "查找通知"},
        )
        for conversation in model._history[2:]:
            assert all("第一版完整正文" not in message.content for message in conversation)
