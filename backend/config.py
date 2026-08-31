from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DEFAULT_CONFIG = CONFIG_DIR / "app_config.json"


class ConfigError(RuntimeError):
    """Raised when the platform configuration cannot be loaded."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"configuration file is invalid JSON: {path}") from exc

    if not isinstance(payload, dict):
        raise ConfigError("configuration root must be an object")
    return payload


def load_config(path: Path | None = None) -> dict[str, Any]:
    return _read_json(path or DEFAULT_CONFIG)


def public_config(config: dict[str, Any]) -> dict[str, Any]:
    model = config.get("model", {})
    storage = config.get("storage", {})
    security = config.get("security", {})
    return {
        "app": config.get("app", {}),
        "model": {
            "enabled": bool(model.get("enabled")),
            "provider": model.get("provider", "custom"),
            "base_url_configured": bool(model.get("base_url")),
            "api_key_configured": bool(model.get("api_key")),
            "chat_model": model.get("chat_model", ""),
            "embedding_model": model.get("embedding_model", ""),
            "timeout_seconds": model.get("timeout_seconds", 30),
        },
        "storage": {
            "data_dir": storage.get("data_dir", "data"),
            "upload_dir": storage.get("upload_dir", "data/uploads"),
        },
        "security": {
            "data_boundary": security.get("data_boundary", "本地安全域"),
            "audit_enabled": bool(security.get("audit_enabled", True)),
            "manual_approval_required": bool(security.get("manual_approval_required", True)),
        },
    }
