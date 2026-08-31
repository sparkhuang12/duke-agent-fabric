from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables prefixed with ``DUKE_``."""

    model_config = SettingsConfigDict(
        env_prefix="DUKE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "duke-agent-fabric"
    environment: Literal["development", "test", "staging", "production"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=9090, ge=1, le=65535)
    log_level: str = "INFO"
    data_dir: Path = PROJECT_ROOT / "data"
    database_url: str = "sqlite:///data/harness.db"
    redis_url: SecretStr = SecretStr("")

    model_api_base: str = ""
    model_api_key: SecretStr = SecretStr("")
    model_name: str = ""
    model_fallbacks: str = ""
    model_timeout_seconds: float = Field(default=45.0, gt=0, le=300)
    model_max_retries: int = Field(default=2, ge=0, le=8)
    model_temperature: float = Field(default=0.1, ge=0, le=2)
    model_allowed_hosts: str = ""

    opa_url: str = "http://opa:8181"
    opa_decision_path: str = "/v1/data/duke/harness/decision"
    opa_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    opa_failure_mode: Literal["closed", "open"] = "closed"
    opa_embedded_development_fallback: bool = True
    opa_allowed_hosts: str = ""
    storage_allowed_hosts: str = ""

    context_recent_messages: int = Field(default=12, ge=2, le=100)
    context_max_chars: int = Field(default=24000, ge=2000, le=200000)
    context_summary_chars: int = Field(default=4000, ge=500, le=20000)
    short_term_retention_days: int = Field(default=7, ge=1, le=30)
    long_term_retention_days: int = Field(default=365, ge=30, le=3650)

    max_graph_steps: int = Field(default=12, ge=2, le=100)
    max_tool_calls: int = Field(default=6, ge=0, le=50)
    max_run_seconds: int = Field(default=180, ge=5, le=3600)
    execution_workers: int = Field(default=8, ge=1, le=128)
    max_pending_runs: int = Field(default=32, ge=1, le=10000)
    circuit_breaker_threshold: int = Field(default=5, ge=1, le=100)
    circuit_breaker_cooldown_seconds: int = Field(default=30, ge=1, le=3600)

    agent_config_path: Path = PROJECT_ROOT / "config" / "agents.json"
    skills_manifest_path: Path = PROJECT_ROOT / "skills" / "manifest.json"
    static_dir: Path = PROJECT_ROOT / "prototype"
    expose_legacy_api: bool = True

    auth_mode: Literal["development_headers", "trusted_proxy", "oidc"] = "development_headers"
    trusted_proxy_secret: SecretStr = SecretStr("")
    oidc_issuer: str = ""
    oidc_audience: str = "duke-agent-fabric"
    oidc_jwks_url: str = ""
    oidc_allowed_hosts: str = ""
    oidc_tenant_claim: str = "tenant_id"
    oidc_department_claim: str = "department"
    oidc_roles_claim: str = "realm_access.roles"
    oidc_clearance_claim: str = "clearance"
    oidc_jwks_cache_seconds: int = Field(default=300, ge=30, le=3600)
    oidc_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    oidc_algorithms: str = "RS256,ES256"

    @property
    def allowed_oidc_algorithms(self) -> list[str]:
        return [item.strip() for item in self.oidc_algorithms.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def model_configured(self) -> bool:
        return bool(self.model_api_base and self.model_api_key.get_secret_value() and self.model_name)

    @property
    def fallback_model_names(self) -> list[str]:
        return [item.strip() for item in self.model_fallbacks.split(",") if item.strip()]

    @property
    def allowed_model_hosts(self) -> set[str]:
        return {item.strip().lower() for item in self.model_allowed_hosts.split(",") if item.strip()}

    @property
    def allowed_oidc_hosts(self) -> set[str]:
        return {item.strip().lower() for item in self.oidc_allowed_hosts.split(",") if item.strip()}

    @property
    def redis_connection_url(self) -> str:
        return self.redis_url.get_secret_value()

    @staticmethod
    def _host_set(value: str) -> set[str]:
        return {item.strip().lower() for item in value.split(",") if item.strip()}

    @property
    def short_term_ttl_seconds(self) -> int:
        return self.short_term_retention_days * 24 * 60 * 60

    @property
    def short_term_ttl_minutes(self) -> int:
        return self.short_term_retention_days * 24 * 60

    @model_validator(mode="after")
    def validate_production_guards(self) -> Settings:
        if self.is_production:
            errors: list[str] = []
            if self.auth_mode != "oidc":
                errors.append("OIDC authentication is required")
            if not self.oidc_issuer or not self.oidc_jwks_url or not self.oidc_audience:
                errors.append("OIDC issuer, JWKS URL and audience must be configured")
            jwks_host = (urlparse(self.oidc_jwks_url).hostname or "").lower()
            if not jwks_host or jwks_host not in self.allowed_oidc_hosts:
                errors.append("OIDC JWKS host must be explicitly allow-listed")
            if self.opa_failure_mode != "closed":
                errors.append("OPA must fail closed")
            if self.opa_embedded_development_fallback:
                errors.append("embedded OPA fallback must be disabled")
            opa_host = (urlparse(self.opa_url).hostname or "").lower()
            if not opa_host or opa_host not in self._host_set(self.opa_allowed_hosts):
                errors.append("OPA host must be explicitly allow-listed")
            if not self.database_url.startswith(("mysql+pymysql://", "mysql://")):
                errors.append("MySQL is required for long-term persistence")
            if not self.redis_connection_url.startswith(("redis://", "rediss://")):
                errors.append("Redis is required for short-term context and checkpoints")
            storage_hosts = self._host_set(self.storage_allowed_hosts)
            mysql_host = (urlparse(self.database_url).hostname or "").lower()
            redis_host = (urlparse(self.redis_connection_url).hostname or "").lower()
            if not mysql_host or not redis_host or not {mysql_host, redis_host}.issubset(storage_hosts):
                errors.append("MySQL and Redis hosts must be explicitly allow-listed")
            if self.short_term_retention_days != 7 or self.long_term_retention_days != 365:
                errors.append("production retention must be 7 days short-term and 365 days long-term")
            if not self.model_configured:
                errors.append("model API must be configured")
            model_host = (urlparse(self.model_api_base).hostname or "").lower()
            if not model_host or model_host not in self.allowed_model_hosts:
                errors.append("model gateway host must be explicitly allow-listed")
            tracing_enabled = any(
                os.getenv(name, "").lower() in {"1", "true", "yes", "on"}
                for name in ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING")
            )
            if tracing_enabled:
                errors.append("external LangChain/LangSmith tracing is forbidden by the data residency policy")
            if errors:
                raise ValueError("invalid production configuration: " + "; ".join(errors))
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
