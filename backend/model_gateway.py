from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class ModelGatewayError(RuntimeError):
    """Raised when a configured model gateway call fails."""


def _model_ready(model_config: dict[str, Any]) -> bool:
    return bool(
        model_config.get("enabled")
        and model_config.get("base_url")
        and model_config.get("api_key")
        and model_config.get("chat_model")
    )


def gateway_status(config: dict[str, Any]) -> dict[str, Any]:
    model = config.get("model", {})
    return {
        "enabled": bool(model.get("enabled")),
        "ready": _model_ready(model),
        "provider": model.get("provider", "custom"),
        "base_url_configured": bool(model.get("base_url")),
        "api_key_configured": bool(model.get("api_key")),
        "chat_model": model.get("chat_model", ""),
        "embedding_model": model.get("embedding_model", ""),
    }


def call_chat_model(config: dict[str, Any], messages: list[dict[str, str]]) -> dict[str, Any]:
    model = config.get("model", {})
    if not _model_ready(model):
        return {
            "configured": False,
            "status": "model_api_not_configured",
            "message": "模型 API 尚未配置。请在 config/app_config.json 中补充 base_url、api_key、chat_model 并启用 enabled。",
            "choices": [],
        }

    endpoint = str(model["base_url"]).rstrip("/") + "/chat/completions"
    payload = {
        "model": model["chat_model"],
        "messages": messages,
        "temperature": model.get("temperature", 0.2),
        "stream": False,
    }
    timeout = int(model.get("timeout_seconds", 30))
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {model['api_key']}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ModelGatewayError(f"model gateway HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ModelGatewayError(f"model gateway unavailable: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ModelGatewayError("model gateway returned invalid JSON") from exc


def run_agent_prompt(config: dict[str, Any], agent: dict[str, Any], prompt: str) -> dict[str, Any]:
    system_prompt = (
        "你是政务办公智能体平台中的一个可控业务智能体。"
        "输出必须保留来源核验、人工确认和审计留痕提示。"
    )
    user_prompt = f"智能体：{agent['name']}\n任务：{prompt}\n请基于该智能体职责给出结构化处理结果。"
    return call_chat_model(
        config,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
