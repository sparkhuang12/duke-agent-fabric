from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from typing import Any, TypeVar

T = TypeVar("T")


class BoundedWorkPool:
    """Runs blocking graphs off the API loop with bounded admission.

    The small polling interval intentionally avoids depending on event-loop
    callbacks from provider/graph worker threads. Cancellation stops waiting;
    provider timeouts and graph deadlines bound the underlying work.
    """

    def __init__(self, *, workers: int, max_pending: int):
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="duke-run")
        # A threading semaphore can be released directly by a Future callback.
        # That keeps the slot occupied even if the HTTP coroutine is cancelled
        # while its provider/graph work is still running.
        self._capacity = threading.BoundedSemaphore(max_pending)

    async def run(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        while not self._capacity.acquire(blocking=False):
            await asyncio.sleep(0.01)
        try:
            future: Future[T] = self._executor.submit(partial(func, *args, **kwargs))
        except BaseException:
            self._capacity.release()
            raise
        future.add_done_callback(lambda _: self._capacity.release())
        while not future.done():
            await asyncio.sleep(0.01)
        return future.result()

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
