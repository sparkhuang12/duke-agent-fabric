from __future__ import annotations

from typing import Any

from duke_harness.context.models import StoredMessage
from duke_harness.domain import ContextAddress, new_id, utc_now


class RedisShortTermRepository:
    """Seven-day conversation store isolated by the hashed context namespace."""

    def __init__(self, redis_url: str, *, ttl_seconds: int, client: Any | None = None):
        if client is None:
            try:
                from redis import Redis
            except ImportError as exc:  # pragma: no cover - production optional dependency
                raise RuntimeError("install duke-agent-fabric[production] for Redis support") from exc
            client = Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                health_check_interval=30,
            )
        self._client: Any = client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _keys(address: ContextAddress) -> tuple[str, str, str]:
        prefix = f"duke:short:v1:{address.namespace}"
        return f"{prefix}:messages", f"{prefix}:order", f"{prefix}:summary"

    def append_message(
        self,
        address: ContextAddress,
        *,
        role: str,
        content: str,
        run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> StoredMessage:
        message = StoredMessage(
            id=new_id("msg"),
            role=role,  # type: ignore[arg-type]
            content=content,
            run_id=run_id,
            metadata=metadata or {},
            created_at=utc_now(),
        )
        messages_key, order_key, _ = self._keys(address)
        self._purge_expired(messages_key, order_key, message.created_at.timestamp())
        field = f"{run_id}:{role}"
        pipeline = self._client.pipeline(transaction=True)
        pipeline.hsetnx(messages_key, field, message.model_dump_json())
        pipeline.zadd(order_key, {field: message.created_at.timestamp()}, nx=True)
        pipeline.expire(messages_key, self.ttl_seconds)
        pipeline.expire(order_key, self.ttl_seconds)
        pipeline.execute()
        return message

    def recent_messages(self, address: ContextAddress, limit: int) -> list[StoredMessage]:
        messages_key, order_key, _ = self._keys(address)
        self._purge_expired(messages_key, order_key, utc_now().timestamp())
        fields: list[str] = self._client.zrevrange(order_key, 0, max(limit - 1, 0))
        if not fields:
            return []
        payloads: list[str | None] = self._client.hmget(messages_key, fields)
        messages = [StoredMessage.model_validate_json(item) for item in payloads if item]
        return list(reversed(messages))

    def message_count(self, address: ContextAddress) -> int:
        messages_key, order_key, _ = self._keys(address)
        self._purge_expired(messages_key, order_key, utc_now().timestamp())
        return int(self._client.zcard(order_key))

    def get_summary(self, address: ContextAddress) -> str:
        _, _, summary_key = self._keys(address)
        value = self._client.get(summary_key)
        return str(value) if value else ""

    def set_summary(self, address: ContextAddress, summary: str) -> None:
        _, _, summary_key = self._keys(address)
        self._client.set(summary_key, summary, ex=self.ttl_seconds)

    def ready(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def close(self) -> None:
        self._client.close()

    def _purge_expired(self, messages_key: str, order_key: str, now_timestamp: float) -> None:
        cutoff = now_timestamp - self.ttl_seconds
        expired: list[str] = self._client.zrangebyscore(order_key, "-inf", cutoff)
        if not expired:
            return
        pipeline = self._client.pipeline(transaction=True)
        pipeline.hdel(messages_key, *expired)
        pipeline.zrem(order_key, *expired)
        pipeline.execute()

    def debug_ttl(self, address: ContextAddress) -> dict[str, int]:
        """Return key TTLs for diagnostics without exposing conversation content."""
        names = ("messages", "order", "summary")
        return {name: int(self._client.ttl(key)) for name, key in zip(names, self._keys(address), strict=True)}
