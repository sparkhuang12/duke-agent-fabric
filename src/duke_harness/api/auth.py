from __future__ import annotations

import hmac
from typing import cast

from fastapi import Header, HTTPException, Request, status

from duke_harness.config import Settings
from duke_harness.domain import Principal


async def principal_from_headers(
    request: Request,
    x_duke_tenant: str = Header(default=""),
    x_duke_user: str = Header(default=""),
    x_duke_roles: str = Header(default="user"),
    x_duke_department: str = Header(default=""),
    x_duke_clearance: str = Header(default="internal"),
    x_duke_proxy_token: str = Header(default=""),
    authorization: str = Header(default=""),
) -> Principal:
    settings: Settings = request.app.state.runtime.settings
    if settings.auth_mode == "oidc":
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token is required")
        try:
            return cast(
                Principal,
                request.app.state.runtime.identity.authenticate(authorization.removeprefix("Bearer ").strip()),
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    if settings.auth_mode == "trusted_proxy":
        expected = settings.trusted_proxy_secret.get_secret_value()
        if not expected or not hmac.compare_digest(x_duke_proxy_token, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid trusted proxy token")
    if not x_duke_tenant or not x_duke_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Duke-Tenant and X-Duke-User headers are required",
        )
    return Principal(
        tenant_id=x_duke_tenant,
        user_id=x_duke_user,
        roles=[item.strip() for item in x_duke_roles.split(",") if item.strip()],
        department=x_duke_department,
        clearance=x_duke_clearance,
    )
