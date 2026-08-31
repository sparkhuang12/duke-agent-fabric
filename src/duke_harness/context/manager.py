from __future__ import annotations

from duke_harness.context.models import ContextSnapshot, MemoryItem, StoredMessage
from duke_harness.context.repository import ContextRepository
from duke_harness.domain import ContextAddress

SECURITY_RANKS = {"public": 0, "internal": 1, "confidential": 2, "secret": 3}


class ContextManager:
    """Builds bounded prompts while keeping every agent/thread namespace isolated."""

    def __init__(
        self,
        repository: ContextRepository,
        *,
        recent_messages: int = 12,
        max_chars: int = 24_000,
        summary_chars: int = 4_000,
    ):
        self.repository = repository
        self.recent_messages = recent_messages
        self.max_chars = max_chars
        self.summary_chars = summary_chars

    def load(self, address: ContextAddress, query: str, *, clearance: str = "secret") -> ContextSnapshot:
        clearance_rank = SECURITY_RANKS.get(clearance, 1)
        summary = self.repository.get_summary(address) if clearance_rank >= SECURITY_RANKS["internal"] else ""
        messages = [
            item
            for item in self.repository.recent_messages(address, self.recent_messages)
            if SECURITY_RANKS.get(str(item.metadata.get("security_level", "internal")), 1) <= clearance_rank
        ]
        memories = [
            item
            for item in self.repository.search_memories(address, query, limit=6)
            if SECURITY_RANKS.get(str(item.metadata.get("security_level", "internal")), 1) <= clearance_rank
        ]
        char_count = (
            len(summary) + sum(len(item.content) for item in messages) + sum(len(item.content) for item in memories)
        )
        truncated = char_count > self.max_chars
        if truncated:
            summary, messages, memories = self._fit_budget(summary, messages, memories)
            char_count = (
                len(summary) + sum(len(item.content) for item in messages) + sum(len(item.content) for item in memories)
            )
        return ContextSnapshot(
            namespace=address.namespace,
            summary=summary,
            recent_messages=messages,
            memories=memories,
            truncated=truncated,
            char_count=char_count,
        )

    def record_turn(
        self,
        address: ContextAddress,
        run_id: str,
        user_input: str,
        assistant_output: str,
        *,
        memory_scope: str = "short_term",
        security_level: str = "internal",
    ) -> None:
        message_metadata = {"security_level": security_level}
        self.repository.append_message(
            address, role="user", content=user_input, run_id=run_id, metadata=message_metadata
        )
        self.repository.append_message(
            address, role="assistant", content=assistant_output, run_id=run_id, metadata=message_metadata
        )
        if memory_scope == "long_term":
            content = f"User: {user_input}\nAssistant: {assistant_output}"[: self.max_chars]
            self.repository.add_memory(
                address,
                content=content,
                kind="episodic",
                importance=0.6,
                metadata={"run_id": run_id, "security_level": security_level, "approved": True},
            )
        self._compact_if_needed(address)

    def _compact_if_needed(self, address: ContextAddress) -> None:
        count = self.repository.message_count(address)
        if count <= self.recent_messages * 2:
            return
        older = self.repository.recent_messages(address, self.recent_messages * 3)[: self.recent_messages]
        if any(
            SECURITY_RANKS.get(str(item.metadata.get("security_level", "internal")), 1) > SECURITY_RANKS["internal"]
            for item in older
        ):
            return
        lines = [f"{item.role}: {item.content[:500]}" for item in older]
        summary = "\n".join(line for line in lines if line).strip()[-self.summary_chars :]
        self.repository.set_summary(address, summary)

    def _fit_budget(
        self,
        summary: str,
        messages: list[StoredMessage],
        memories: list[MemoryItem],
    ) -> tuple[str, list[StoredMessage], list[MemoryItem]]:
        remaining = self.max_chars
        fitted_summary = summary[-min(len(summary), self.summary_chars, remaining) :]
        remaining -= len(fitted_summary)
        fitted_messages: list[StoredMessage] = []
        for message in reversed(messages):
            if len(message.content) > remaining:
                continue
            fitted_messages.append(message)
            remaining -= len(message.content)
        fitted_messages.reverse()
        fitted_memories = []
        for memory in memories:
            if len(memory.content) > remaining:
                continue
            fitted_memories.append(memory)
            remaining -= len(memory.content)
        return fitted_summary, fitted_messages, fitted_memories
