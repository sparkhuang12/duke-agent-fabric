from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver


class CheckpointHandle:
    def __init__(self, saver: Any, manager: AbstractContextManager[Any] | None = None):
        self.saver = saver
        self._manager = manager

    def close(self) -> None:
        if self._manager is not None:
            self._manager.__exit__(None, None, None)


def create_checkpointer(redis_url: str, *, production: bool, ttl_minutes: int) -> CheckpointHandle:
    if redis_url.startswith(("redis://", "rediss://")):
        try:
            from langgraph.checkpoint.redis import RedisSaver
        except ImportError as exc:  # pragma: no cover - production optional dependency
            raise RuntimeError("install duke-agent-fabric[production] for Redis checkpoints") from exc
        manager = RedisSaver.from_conn_string(
            redis_url,
            ttl={"default_ttl": ttl_minutes, "refresh_on_read": False},
        )
        saver = manager.__enter__()
        saver.setup()
        return CheckpointHandle(saver, manager)
    if production:
        raise RuntimeError("production requires Redis checkpoints")
    return CheckpointHandle(InMemorySaver())
