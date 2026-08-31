from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from backend.data_store import (
    create_document,
    create_task,
    get_agent,
    get_dashboard,
    get_knowledge,
    get_roadmap,
    list_agents,
    list_audit_logs,
    list_documents,
    list_tasks,
    search_documents,
    update_task_status,
)

router = APIRouter(tags=["legacy"])


@router.get("/api/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "service": "duke-agent-fabric"}


@router.get("/api/dashboard")
async def dashboard() -> dict[str, Any]:
    return get_dashboard()


@router.get("/api/agents")
async def agents(q: str = "") -> dict[str, Any]:
    items = list_agents()
    if q:
        items = [item for item in items if q in f"{item['name']}{item['summary']}{item['desc']}"]
    return {"items": items}


@router.get("/api/agents/{agent_id}")
async def agent(agent_id: str) -> dict[str, Any]:
    item = get_agent(agent_id)
    if item is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return item


@router.get("/api/config/public")
async def public_config(request: Request) -> dict[str, Any]:
    settings = request.app.state.runtime.settings
    return {
        "app": {"name": "Duke Agent Fabric", "environment": settings.environment},
        "model": {
            "enabled": settings.model_configured,
            "provider": "openai-compatible",
            "base_url_configured": bool(settings.model_api_base),
            "api_key_configured": bool(settings.model_api_key.get_secret_value()),
            "chat_model": settings.model_name,
        },
        "storage": {"data_dir": str(settings.data_dir)},
        "security": {
            "data_boundary": "policy-governed local domain",
            "audit_enabled": True,
            "manual_approval_required": True,
        },
    }


@router.get("/api/model/status")
async def model_status(request: Request) -> dict[str, Any]:
    model = request.app.state.runtime.models.status()
    return {
        "enabled": model["configured"],
        "ready": model["configured"],
        "provider": "openai-compatible",
        "base_url_configured": bool(request.app.state.runtime.settings.model_api_base),
        "api_key_configured": bool(request.app.state.runtime.settings.model_api_key.get_secret_value()),
        "chat_model": request.app.state.runtime.settings.model_name,
        "fallbacks": request.app.state.runtime.settings.fallback_model_names,
    }


@router.post("/api/agents/{agent_id}/run")
async def legacy_agent_run(agent_id: str, payload: dict[str, Any], request: Request) -> dict[str, Any]:
    from duke_harness.domain import Principal, RunRequest

    runtime = request.app.state.runtime
    prompt = str(payload.get("prompt") or payload.get("input") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="请提供 prompt 或 input")
    if runtime.agents.get(agent_id) is None:
        raise HTTPException(status_code=404, detail="智能体不存在")
    if not runtime.models.ready:
        model = {
            "configured": False,
            "status": "model_api_not_configured",
            "message": "模型 API 尚未配置。请设置 DUKE_MODEL_API_BASE、DUKE_MODEL_API_KEY 和 DUKE_MODEL_NAME。",
            "choices": [],
        }
    else:
        record = runtime.runner.start(
            Principal(tenant_id="legacy", user_id="legacy-user", roles=["user"]),
            RunRequest(agent_id=agent_id, input=prompt),
        )
        model = {
            "configured": True,
            "status": record.status.value,
            "choices": [{"message": {"role": "assistant", "content": record.output}}] if record.output else [],
            "run_id": record.run_id,
        }
    return {
        "agent": get_agent(agent_id),
        "input": prompt,
        "model": model,
        "review_required": True,
        "audit": ["OPA 策略", "上下文隔离", "来源核验", "人工确认", "操作留痕"],
    }


@router.get("/api/knowledge")
async def knowledge() -> dict[str, Any]:
    return {"items": get_knowledge()}


@router.post("/api/knowledge/search")
async def knowledge_search(payload: dict[str, Any]) -> dict[str, Any]:
    return search_documents(payload)


@router.get("/api/documents")
async def documents() -> dict[str, Any]:
    return {"items": list_documents()}


@router.post("/api/documents", status_code=status.HTTP_201_CREATED)
async def document_create(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return create_document(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/api/tasks")
async def tasks() -> dict[str, Any]:
    return {"items": list_tasks()}


@router.post("/api/tasks", status_code=status.HTTP_201_CREATED)
async def task_create(payload: dict[str, Any]) -> dict[str, Any]:
    return create_task(payload)


@router.post("/api/tasks/{task_id}/approve")
async def task_approve(task_id: str) -> dict[str, Any]:
    item = update_task_status(task_id, "approved")
    if item is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return item


@router.get("/api/audit-logs")
async def audit_logs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return {"items": list_audit_logs()[:limit]}


@router.get("/api/roadmap")
async def roadmap() -> dict[str, Any]:
    return get_roadmap()
