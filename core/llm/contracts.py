from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class LLMMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class LLMRequest:
    """Canonical request contract for all LLM providers."""

    messages: list[LLMMessage]
    model: str
    temperature: float = 0.4
    top_p: float = 1.0
    max_tokens: int = 450
    timeout_s: float = 20.0
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class LLMResponse:
    content: str
    finish_reason: str = "stop"
    usage: LLMUsage | None = None
    raw: dict[str, Any] | None = None

    @property
    def text(self) -> str:
        """Compatibility alias for older code paths.

        Canonical field name is ``content``.  Keep ``text`` as a read-only
        alias so legacy callers do not fork a second response shape.
        """
        return str(self.content or "")


class LLMClient(Protocol):
    """Minimal client contract shared across provider implementations."""

    async def generate(self, req: LLMRequest) -> LLMResponse:
        ...

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        ...
