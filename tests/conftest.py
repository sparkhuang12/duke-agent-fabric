from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr

from duke_harness.config import PROJECT_ROOT, Settings


class ScriptedChatModel(BaseChatModel):
    _responses: list[AIMessage] = PrivateAttr()

    def __init__(self, responses: list[AIMessage]):
        super().__init__()
        self._responses = list(responses)

    @property
    def _llm_type(self) -> str:
        return "scripted-test-model"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001, ANN201
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ANN001
        if not self._responses:
            raise AssertionError("scripted model has no response left")
        return ChatResult(generations=[ChatGeneration(message=self._responses.pop(0))])


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        data_dir=tmp_path,
        database_url=f"sqlite:///{tmp_path / 'harness.db'}",
        model_name="fake",
        agent_config_path=PROJECT_ROOT / "config" / "agents.json",
        skills_manifest_path=PROJECT_ROOT / "skills" / "manifest.json",
        static_dir=PROJECT_ROOT / "prototype",
        opa_url="http://127.0.0.1:1",
        opa_embedded_development_fallback=True,
        expose_legacy_api=True,
    )
