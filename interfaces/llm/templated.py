from __future__ import annotations

import random
from dataclasses import dataclass
from collections.abc import Sequence

from .base import LLMClient, LLMMessage, LLMResponse


@dataclass
class TemplatedLLM(LLMClient):
    """
    Safe fallback LLM: returns a deterministic-ish template response.
    This keeps the system functional without any external API.
    """

    seed: int = 7

    def complete(
        self,
        *,
        messages: Sequence[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> LLMResponse:
        rnd = random.Random(self.seed)
        user_text = ""
        for m in messages:
            if m.role == "user":
                user_text = m.content
        # Very small heuristic templates
        variants = [
            "Коротко и по делу: {x}",
            "Дружелюбно: {x}",
            "Профессионально: {x}",
        ]
        frame = rnd.choice(variants)
        out = frame.format(x=user_text.strip()[: max(80, min(300, len(user_text)))])
        return LLMResponse(text=out, raw={"mode": "templated"})
