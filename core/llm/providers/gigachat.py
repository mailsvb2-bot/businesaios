from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.llm.contracts import LLMClient, LLMRequest, LLMResponse, LLMUsage

GigaChatTransport = Callable[[str, str, dict[str, Any], int], dict[str, Any]]


@dataclass(frozen=True)
class GigaChatClient(LLMClient):
    """GigaChat chat completions client (pure, transport-injected)."""

    transport: GigaChatTransport
    base_url: str
    api_key: str
    model: str
    timeout_s: int = 20

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        model = str(req.model or "").strip() or self.model
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": str(message.content or "")[:8000]}
                for message in req.messages
            ],
            "temperature": float(req.temperature or 0.2),
            "top_p": float(req.top_p or 1.0),
            "max_tokens": int(req.max_tokens or 450),
        }
        raw = self.transport(
            str(self.base_url).rstrip("/") + "/chat/completions",
            self.api_key,
            payload,
            int(req.timeout_s or self.timeout_s),
        )
        return LLMResponse(
            content=_extract_text(raw),
            finish_reason=_extract_finish(raw),
            usage=_extract_usage(raw),
            raw=(raw if isinstance(raw, dict) else None),
        )

    async def generate(self, req: LLMRequest) -> LLMResponse:
        return await asyncio.to_thread(self.generate_sync, req)


def _extract_text(raw: dict[str, Any]) -> str:
    choices = raw.get("choices") or []
    if isinstance(choices, list) and choices:
        msg = (choices[0] or {}).get("message") or {}
        return str(msg.get("content") or "").strip()
    return str(raw.get("output_text") or "").strip()


def _extract_usage(raw: dict[str, Any]) -> LLMUsage | None:
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        return None
    pt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    ct = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    tt = int(usage.get("total_tokens") or (pt + ct) or 0)
    return LLMUsage(prompt_tokens=pt, completion_tokens=ct, total_tokens=tt)


def _extract_finish(raw: dict[str, Any]) -> str:
    choices = raw.get("choices") or []
    if isinstance(choices, list) and choices:
        finish = (choices[0] or {}).get("finish_reason")
        if finish is not None:
            return str(finish)
    return str(raw.get("finish_reason") or "stop")


def build_gigachat(*, transport: GigaChatTransport, base_url: str, api_key: str, model: str, timeout_s: int = 20) -> GigaChatClient:
    return GigaChatClient(
        transport=transport,
        base_url=str(base_url).strip().rstrip("/"),
        api_key=str(api_key).strip(),
        model=str(model).strip(),
        timeout_s=int(timeout_s),
    )
