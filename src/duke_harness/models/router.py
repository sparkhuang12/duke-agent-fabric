from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from duke_harness.config import Settings
from duke_harness.resilience.circuit_breaker import CircuitBreaker, CircuitOpenError
from duke_harness.resilience.errors import ModelNotConfiguredError, ModelUnavailableError


class ModelRouter:
    """OpenAI-compatible model router with retry, fallback and circuit breaking."""

    def __init__(
        self,
        settings: Settings,
        *,
        models: dict[str, BaseChatModel] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self._http_client = httpx.Client(trust_env=False, follow_redirects=False)
        self._models = models or self._build_models(settings)
        self._sleep = sleep
        self.breaker = CircuitBreaker(
            settings.circuit_breaker_threshold,
            settings.circuit_breaker_cooldown_seconds,
        )

    def _build_models(self, settings: Settings) -> dict[str, BaseChatModel]:
        if not settings.model_configured:
            return {}
        names = [settings.model_name, *settings.fallback_model_names]
        return {
            name: ChatOpenAI(
                model=name,
                base_url=settings.model_api_base,
                api_key=settings.model_api_key,
                temperature=settings.model_temperature,
                timeout=settings.model_timeout_seconds,
                max_retries=0,
                http_client=self._http_client,
            )
            for name in names
        }

    @property
    def ready(self) -> bool:
        return bool(self._models)

    def invoke(self, messages: Sequence[BaseMessage], tools: Sequence[BaseTool]) -> BaseMessage:
        if not self._models:
            raise ModelNotConfiguredError("model API is not configured")
        failures: list[str] = []
        for name, configured_model in self._models.items():
            model = configured_model.bind_tools(list(tools)) if tools else configured_model
            for attempt in range(self.settings.model_max_retries + 1):
                try:
                    self.breaker.before_call(name)
                    result = model.invoke(list(messages))
                    self.breaker.record_success(name)
                    return result
                except CircuitOpenError as exc:
                    failures.append(str(exc))
                    break
                except Exception as exc:  # provider SDKs expose different transient exception types
                    self.breaker.record_failure(name)
                    failures.append(f"{name} attempt {attempt + 1}: {type(exc).__name__}")
                    if attempt < self.settings.model_max_retries:
                        self._sleep(min(0.25 * (2**attempt), 2.0))
        raise ModelUnavailableError("all configured models failed: " + "; ".join(failures))

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.ready,
            "models": list(self._models),
            "circuits": self.breaker.snapshot(),
        }

    def close(self) -> None:
        self._http_client.close()
