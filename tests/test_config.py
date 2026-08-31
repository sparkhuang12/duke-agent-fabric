from __future__ import annotations

import pytest
from pydantic import ValidationError

from duke_harness.config import Settings


def test_production_fails_fast_without_required_controls() -> None:
    with pytest.raises(ValidationError, match="invalid production configuration"):
        Settings(environment="production")


def test_production_accepts_explicit_fail_closed_controls() -> None:
    settings = Settings(
        environment="production",
        database_url="mysql+pymysql://duke:password@mysql/duke",
        redis_url="redis://:password@redis:6379/0",
        storage_allowed_hosts="mysql,redis",
        model_api_base="http://llm-gateway:4000/v1",
        model_api_key="secret",
        model_name="approved-model",
        model_allowed_hosts="llm-gateway",
        auth_mode="oidc",
        oidc_issuer="https://sso.example/realms/duke",
        oidc_jwks_url="http://keycloak:8080/realms/duke/protocol/openid-connect/certs",
        oidc_allowed_hosts="keycloak",
        opa_failure_mode="closed",
        opa_url="http://opa:8181",
        opa_allowed_hosts="opa",
        opa_embedded_development_fallback=False,
        expose_legacy_api=False,
    )
    assert settings.is_production is True
    assert settings.short_term_ttl_seconds == 604800
