from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: str  # "system"|"user"|"assistant"
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    raw: dict[str, Any] | None = None


class LLMClient(Protocol):
    """
    A minimal LLM client interface.
    Implementations may call external APIs via sealed effects in runtime,
    or operate locally (templates).
    """

    def complete(
        self,
        *,
        messages: Sequence[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> LLMResponse:
        ...
