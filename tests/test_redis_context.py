from __future__ import annotations

import fakeredis

from duke_harness.context.repository_redis import RedisShortTermRepository
from duke_harness.domain import ContextAddress


def test_redis_short_term_context_is_namespaced_and_expires() -> None:
    client = fakeredis.FakeRedis(decode_responses=True)
    repository = RedisShortTermRepository("redis://unused", ttl_seconds=604800, client=client)
    first = ContextAddress(tenant_id="tenant-a", user_id="alice", agent_id="search", thread_id="same")
    second = ContextAddress(tenant_id="tenant-a", user_id="alice", agent_id="policy", thread_id="same")

    repository.append_message(first, role="user", content="private", run_id="run-1")
    repository.set_summary(first, "summary")

    assert repository.recent_messages(first, 10)[0].content == "private"
    assert repository.recent_messages(second, 10) == []
    assert repository.get_summary(second) == ""
    assert all(value == 604800 for value in repository.debug_ttl(first).values())
