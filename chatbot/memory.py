"""Session memory management for chat history."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionMemory:
    """In-session rolling memory of recent conversation messages."""

    max_messages: int = 10
    messages: list[dict[str, str]] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        """Add a message and keep only the latest max_messages items."""
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]

    def recent(self, limit: int = 10) -> list[dict[str, str]]:
        """Return the latest conversation turns."""
        return self.messages[-limit:]

    def clear(self) -> None:
        """Clear conversation memory."""
        self.messages.clear()
