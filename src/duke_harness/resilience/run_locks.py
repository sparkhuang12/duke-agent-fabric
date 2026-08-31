from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from duke_harness.resilience.errors import RunBusyError


class RunLockManager:
    """Non-blocking per-run leases backed by Redis in distributed deployments."""

    def __init__(self, redis_url: str = "", *, client: Any | None = None):
        if client is None and redis_url.startswith(("redis://", "rediss://")):
            try:
                from redis import Redis
            except ImportError as exc:  # pragma: no cover - production optional dependency
                raise RuntimeError("install duke-agent-fabric[production] for distributed run locks") from exc
            client = Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
                health_check_interval=30,
            )
        self._redis = client
        self._guard = threading.Lock()
        self._local: dict[str, threading.Lock] = {}

    @contextmanager
    def hold(self, run_id: str, *, ttl_seconds: int) -> Iterator[None]:
        if self._redis is not None:
            key = f"duke:run-lock:v1:{run_id}"
            token = uuid.uuid4().hex
            if not self._redis.set(key, token, nx=True, ex=ttl_seconds):
                raise RunBusyError(f"run {run_id} is already being processed")
            try:
                yield
            finally:
                self._release_redis_lease(key, token)
            return

        with self._guard:
            local = self._local.setdefault(run_id, threading.Lock())
        if not local.acquire(blocking=False):
            raise RunBusyError(f"run {run_id} is already being processed")
        try:
            yield
        finally:
            local.release()
            with self._guard:
                if self._local.get(run_id) is local:
                    self._local.pop(run_id, None)

    def close(self) -> None:
        if self._redis is not None:
            self._redis.close()

    def _release_redis_lease(self, key: str, token: str) -> None:
        try:
            from redis.exceptions import RedisError, WatchError
        except ImportError:  # pragma: no cover - client cannot exist without redis package
            return
        client = self._redis
        if client is None:
            return
        while True:
            pipeline = client.pipeline()
            try:
                pipeline.watch(key)
                if pipeline.get(key) != token:
                    pipeline.unwatch()
                    return
                pipeline.multi()
                pipeline.delete(key)
                pipeline.execute()
                return
            except WatchError:
                continue
            except RedisError:
                # Expiry makes the lease safely reacquirable; release failure must not mask the run result.
                return
            finally:
                pipeline.reset()
