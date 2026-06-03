from __future__ import annotations

import random
from dataclasses import dataclass
from collections.abc import Sequence

from core.llm.contracts import LLMClient, LLMMessage, LLMRequest, LLMResponse


@dataclass
class TemplatedLLM(LLMClient):
    """Safe deterministic fallback client used inside core paths.

    Canonical entrypoint is ``generate_sync(LLMRequest)`` / ``generate(LLMRequest)``.
    ``complete(...)`` is preserved as a thin compatibility shim for legacy
    callers that still pass message lists directly.
    """

    seed: int = 7

    def _render_text(self, prompt: str) -> str:
        rnd = random.Random(self.seed)
        variants = [
            "Коротко и по делу: {x}",
            "Дружелюбно: {x}",
            "Профессионально: {x}",
        ]
        frame = rnd.choice(variants)
        text = (prompt or "").strip()
        clipped = text[: max(80, min(300, len(text)))] if text else ""
        return frame.format(x=clipped)

    def _user_text_from_messages(self, messages: Sequence[LLMMessage]) -> str:
        user_parts = [
            m.content
            for m in messages
            if getattr(m, "role", "") == "user" and getattr(m, "content", "")
        ]
        return "\n".join([str(part) for part in user_parts if str(part).strip()]).strip()

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        prompt = self._user_text_from_messages(req.messages)
        return LLMResponse(content=self._render_text(prompt), raw={"mode": "templated"})

    async def generate(self, req: LLMRequest) -> LLMResponse:
        return self.generate_sync(req)

    def complete(
        self,
        *,
        messages: Sequence[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 500,
        json_mode: bool = False,
    ) -> LLMResponse:
        req = LLMRequest(
            messages=[LLMMessage(role=str(m.role), content=str(m.content)) for m in messages],
            model="templated-fallback",
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )
        _ = json_mode
        return self.generate_sync(req)
