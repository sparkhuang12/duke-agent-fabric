from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from duke_harness.api.auth import principal_from_headers
from duke_harness.api.legacy import router as legacy_router
from duke_harness.config import Settings, get_settings
from duke_harness.context.models import ContextSnapshot
from duke_harness.domain import ApprovalRequest, ContextAddress, HealthStatus, Principal, RunRecord, RunRequest
from duke_harness.observability.logging import configure_logging
from duke_harness.observability.metrics import POLICY_DECISIONS, RUN_DURATION, RUNS, TOOL_CALLS
from duke_harness.resilience.errors import HarnessError
from duke_harness.runtime import Runtime

RuntimeFactory = Callable[[Settings], Runtime]
logger = structlog.get_logger("duke_harness.api")


def create_app(settings: Settings | None = None, runtime_factory: RuntimeFactory = Runtime) -> FastAPI:
    configured = settings or get_settings()
    configure_logging(configured.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runtime = runtime_factory(configured)
        try:
            yield
        finally:
            app.state.runtime.close()

    app = FastAPI(
        title="Duke Agent Fabric API",
        version="0.3.0",
        description="Policy-governed execution API for isolated LangGraph agents.",
        docs_url=None if configured.is_production else "/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def request_envelope(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex}")[:128]
        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = (
            "no-store" if request.url.path.startswith("/api/") else "public, max-age=300"
        )
        elapsed_ms = (time.monotonic() - started) * 1000
        response.headers["Server-Timing"] = f"app;dur={elapsed_ms:.1f}"
        logger.info(
            "http.request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=round(elapsed_ms, 2),
        )
        return response

    @app.exception_handler(HarnessError)
    async def harness_error_handler(_: Request, exc: HarnessError) -> JSONResponse:
        code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.retryable else status.HTTP_400_BAD_REQUEST
        if exc.code == "run_not_found":
            code = status.HTTP_404_NOT_FOUND
        elif exc.code == "context_access_denied":
            code = status.HTTP_403_FORBIDDEN
        return JSONResponse(
            status_code=code,
            content={
                "error": {
                    "code": exc.code,
                    "message": str(exc),
                    "retryable": exc.retryable,
                    "stage": exc.stage,
                }
            },
        )

    @app.get("/api/v1/health/live", response_model=HealthStatus, tags=["operations"])
    async def liveness() -> HealthStatus:
        return HealthStatus(status="ok", checks={"process": True})

    @app.get("/api/v1/health/ready", response_model=HealthStatus, tags=["operations"])
    async def readiness(request: Request, response: Response) -> HealthStatus:
        runtime: Runtime = request.app.state.runtime
        opa_ready = await runtime.work_pool.run(runtime.policies.ready)
        checks = {
            "database": runtime.repository.ready(),
            "opa": opa_ready,
            "model": runtime.models.ready,
            "identity": await runtime.work_pool.run(runtime.identity.ready) if runtime.identity else True,
            "agents": len(runtime.agents.list()),
            "skills": len(runtime.skills.list()),
        }
        required = [checks["database"]]
        if runtime.settings.is_production:
            required.extend([checks["opa"], checks["model"], checks["identity"]])
        ready = all(required)
        if not ready:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="ok" if ready else "degraded", checks=checks)

    @app.get("/api/v1/agents", tags=["agents"])
    async def list_agents(
        request: Request,
        _: Principal = Depends(principal_from_headers),
    ) -> dict[str, Any]:
        return {"items": [agent.model_dump(mode="json") for agent in request.app.state.runtime.agents.list()]}

    @app.post("/api/v1/runs", response_model=RunRecord, tags=["runs"])
    async def create_run(
        payload: RunRequest,
        request: Request,
        principal: Principal = Depends(principal_from_headers),
    ) -> RunRecord:
        started = time.monotonic()
        runtime: Runtime = request.app.state.runtime
        record = await runtime.work_pool.run(runtime.runner.start, principal, payload)
        _observe(record, time.monotonic() - started)
        return record

    @app.get("/api/v1/runs/{run_id}", response_model=RunRecord, tags=["runs"])
    async def get_run(
        run_id: str,
        request: Request,
        principal: Principal = Depends(principal_from_headers),
    ) -> RunRecord:
        runtime: Runtime = request.app.state.runtime
        return runtime.runner.get(principal, run_id)

    @app.post("/api/v1/runs/{run_id}/approval", response_model=RunRecord, tags=["runs"])
    async def resolve_approval(
        run_id: str,
        payload: ApprovalRequest,
        request: Request,
        principal: Principal = Depends(principal_from_headers),
    ) -> RunRecord:
        runtime: Runtime = request.app.state.runtime
        record = await runtime.work_pool.run(runtime.runner.resume, principal, run_id, payload)
        _observe(record, 0)
        return record

    @app.get("/api/v1/approvals", tags=["runs"])
    async def pending_approvals(
        request: Request,
        principal: Principal = Depends(principal_from_headers),
        limit: int = 50,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 100))
        runtime: Runtime = request.app.state.runtime
        records = await runtime.work_pool.run(runtime.runner.pending_approvals, principal, safe_limit)
        return {"items": [record.model_dump(mode="json") for record in records]}

    @app.get("/api/v1/contexts/{agent_id}/{thread_id}", response_model=ContextSnapshot, tags=["context"])
    async def inspect_context(
        agent_id: str,
        thread_id: str,
        request: Request,
        principal: Principal = Depends(principal_from_headers),
        q: str = "",
    ) -> ContextSnapshot:
        runtime: Runtime = request.app.state.runtime
        agent = runtime.agents.require(agent_id)
        address = ContextAddress(
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            agent_id=agent_id,
            thread_id=thread_id,
        )
        decision = await runtime.work_pool.run(
            runtime.policies.decide,
            action="context.read",
            principal=principal,
            address=address,
            agent=agent,
            resource={},
            context={},
        )
        if not decision.allow:
            raise HTTPException(status_code=403, detail={"code": "policy_denied", "reasons": decision.reasons})
        return runtime.contexts.load(address, q, clearance=principal.clearance)

    @app.get("/api/v1/tools", tags=["catalog"])
    async def list_tools(
        request: Request,
        _: Principal = Depends(principal_from_headers),
    ) -> dict[str, Any]:
        return {
            "items": [
                {
                    "name": item.name,
                    "description": item.description,
                    "input_schema": item.args_schema.model_json_schema(),
                }
                for item in request.app.state.runtime.tools.list()
            ]
        }

    @app.get("/api/v1/skills", tags=["catalog"])
    async def list_skills(
        request: Request,
        _: Principal = Depends(principal_from_headers),
    ) -> dict[str, Any]:
        return {
            "items": [
                {
                    "name": item.name,
                    "description": item.description,
                    "source_url": item.source_url,
                    "source_commit": item.source_commit,
                    "sha256": item.sha256,
                    "license": item.license,
                }
                for item in request.app.state.runtime.skills.list()
            ]
        }

    @app.get("/api/v1/model/status", tags=["operations"])
    async def current_model_status(
        request: Request,
        _: Principal = Depends(principal_from_headers),
    ) -> dict[str, Any]:
        runtime: Runtime = request.app.state.runtime
        return runtime.models.status()

    @app.get("/api/v1/policy/status", tags=["operations"])
    async def current_policy_status(
        request: Request,
        _: Principal = Depends(principal_from_headers),
    ) -> dict[str, Any]:
        runtime: Runtime = request.app.state.runtime
        return {
            "ready": await runtime.work_pool.run(runtime.policies.ready),
            "failure_mode": runtime.settings.opa_failure_mode,
            "embedded_development_fallback": runtime.settings.opa_embedded_development_fallback,
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    if configured.expose_legacy_api:
        app.include_router(legacy_router)

    static_dir = Path(configured.static_dir)
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="prototype")
    return app


def _observe(record: RunRecord, elapsed: float) -> None:
    RUNS.labels(agent_id=record.address.agent_id, status=record.status.value).inc()
    if elapsed:
        RUN_DURATION.labels(agent_id=record.address.agent_id).observe(elapsed)
    TOOL_CALLS.labels(agent_id=record.address.agent_id).inc(record.usage.get("tool_calls", 0))
    for decision in record.policy_decisions:
        POLICY_DECISIONS.labels(source=decision.source, allow=str(decision.allow).lower()).inc()


app = create_app()
