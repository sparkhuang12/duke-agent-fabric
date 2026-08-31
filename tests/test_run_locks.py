from __future__ import annotations

import fakeredis
import pytest

from duke_harness.resilience.errors import RunBusyError
from duke_harness.resilience.run_locks import RunLockManager


@pytest.mark.parametrize(
    "manager",
    [
        RunLockManager(),
        RunLockManager(client=fakeredis.FakeRedis(decode_responses=True)),
    ],
    ids=["local", "redis"],
)
def test_run_lock_rejects_concurrent_resume_and_releases(manager: RunLockManager) -> None:
    try:
        with (
            manager.hold("run-one", ttl_seconds=30),
            pytest.raises(RunBusyError),
            manager.hold("run-one", ttl_seconds=30),
        ):
            pass
        with manager.hold("run-one", ttl_seconds=30):
            pass
    finally:
        manager.close()
