from __future__ import annotations

import asyncio
import threading

import pytest

from duke_harness.resilience.work_pool import BoundedWorkPool


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_release_background_capacity() -> None:
    pool = BoundedWorkPool(workers=1, max_pending=1)
    first_started = threading.Event()
    release_first = threading.Event()
    second_started = threading.Event()

    def first() -> None:
        first_started.set()
        release_first.wait(timeout=2)

    def second() -> None:
        second_started.set()

    first_task = asyncio.create_task(pool.run(first))
    for _ in range(100):
        if first_started.is_set():
            break
        await asyncio.sleep(0.01)
    assert first_started.is_set()
    first_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first_task

    second_task = asyncio.create_task(pool.run(second))
    await asyncio.sleep(0.05)
    assert not second_started.is_set()

    release_first.set()
    await asyncio.wait_for(second_task, timeout=1)
    assert second_started.is_set()
    pool.close()
