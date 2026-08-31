from __future__ import annotations

import threading
import time
from typing import Any

import httpx
import jwt

from duke_harness.config import Settings
from duke_harness.domain import Principal


class IdentityTokenError(ValueError):
    pass


def _claim(payload: dict[str, Any], path: str, default: Any = "") -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return default
        value = value[part]
    return value


class OIDCAuthenticator:
    """Offline JWT validation with an allow-listed, cached Keycloak/OIDC JWKS endpoint."""

    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self._client = httpx.Client(
            timeout=3.0,
            transport=transport,
            trust_env=False,
            follow_redirects=False,
        )
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def close(self) -> None:
        self._client.close()

    def authenticate(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
            algorithm = str(header.get("alg", ""))
            key_id = str(header.get("kid", ""))
            if algorithm not in self.settings.allowed_oidc_algorithms or not key_id:
                raise IdentityTokenError("token algorithm or key id is not allowed")
            key = self._key(key_id)
            payload = jwt.decode(
                token,
                key=key,
                algorithms=self.settings.allowed_oidc_algorithms,
                audience=self.settings.oidc_audience,
                issuer=self.settings.oidc_issuer,
                leeway=self.settings.oidc_clock_skew_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            roles_value = _claim(payload, self.settings.oidc_roles_claim, [])
            if isinstance(roles_value, str):
                roles = [item.strip() for item in roles_value.split(",") if item.strip()]
            elif isinstance(roles_value, list):
                roles = [str(item) for item in roles_value]
            else:
                roles = []
            tenant_id = str(_claim(payload, self.settings.oidc_tenant_claim, ""))
            if not tenant_id:
                raise IdentityTokenError("token has no authoritative tenant claim")
            return Principal(
                tenant_id=tenant_id,
                user_id=str(payload["sub"]),
                roles=roles,
                department=str(_claim(payload, self.settings.oidc_department_claim, "")),
                clearance=str(_claim(payload, self.settings.oidc_clearance_claim, "internal")),
            )
        except IdentityTokenError:
            raise
        except (jwt.PyJWTError, KeyError, ValueError, httpx.HTTPError) as exc:
            raise IdentityTokenError("invalid identity token") from exc

    def ready(self) -> bool:
        try:
            self._refresh_keys(force=not self._keys)
            return bool(self._keys)
        except (IdentityTokenError, httpx.HTTPError):
            return False

    def _key(self, key_id: str) -> Any:
        if time.monotonic() >= self._expires_at or key_id not in self._keys:
            self._refresh_keys(force=key_id not in self._keys)
        key = self._keys.get(key_id)
        if key is None:
            raise IdentityTokenError("token signing key is unknown")
        return key

    def _refresh_keys(self, *, force: bool) -> None:
        with self._lock:
            if not force and time.monotonic() < self._expires_at:
                return
            response = self._client.get(self.settings.oidc_jwks_url)
            response.raise_for_status()
            payload = response.json()
            keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(keys, list):
                raise IdentityTokenError("OIDC JWKS response is malformed")
            loaded: dict[str, Any] = {}
            for value in keys:
                if not isinstance(value, dict) or not value.get("kid"):
                    continue
                algorithm = str(value.get("alg", ""))
                if algorithm and algorithm not in self.settings.allowed_oidc_algorithms:
                    continue
                loaded[str(value["kid"])] = jwt.PyJWK.from_dict(value).key
            if not loaded:
                raise IdentityTokenError("OIDC JWKS contains no allowed signing keys")
            self._keys = loaded
            self._expires_at = time.monotonic() + self.settings.oidc_jwks_cache_seconds
