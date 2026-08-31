from __future__ import annotations

import threading
import time
from dataclasses import dataclass


class CircuitOpenError(RuntimeError):
    pass


@dataclass
class CircuitState:
    failures: int = 0
    opened_until: float = 0.0


class CircuitBreaker:
    def __init__(self, failure_threshold: int, cooldown_seconds: int):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._states: dict[str, CircuitState] = {}
        self._lock = threading.Lock()

    def before_call(self, key: str) -> None:
        with self._lock:
            state = self._states.setdefault(key, CircuitState())
            now = time.monotonic()
            if state.opened_until > now:
                raise CircuitOpenError(f"circuit is open for {key}")
            if state.opened_until:
                state.failures = 0
                state.opened_until = 0

    def record_success(self, key: str) -> None:
        with self._lock:
            self._states[key] = CircuitState()

    def record_failure(self, key: str) -> None:
        with self._lock:
            state = self._states.setdefault(key, CircuitState())
            state.failures += 1
            if state.failures >= self.failure_threshold:
                state.opened_until = time.monotonic() + self.cooldown_seconds

    def snapshot(self) -> dict[str, dict[str, float | int | bool]]:
        now = time.monotonic()
        with self._lock:
            return {
                key: {
                    "failures": state.failures,
                    "open": state.opened_until > now,
                    "retry_after_seconds": max(0.0, state.opened_until - now),
                }
                for key, state in self._states.items()
            }
