from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ..contracts import LLMClient, LLMRequest, LLMResponse, LLMUsage
from ..redaction import safe_metadata



OpenAICompatTransport = Callable[[str, str, Dict[str, Any], int], Dict[str, Any]]


@dataclass(frozen=True)
class OpenAICompatConfig:
    base_url: str
    api_key: str
    default_model: str = "gpt-4.1-mini"
    transport: Optional[OpenAICompatTransport] = None


class OpenAICompatClient(LLMClient):
    """OpenAI-compatible client (Responses API preferred).

    Network is executed by `transport` wired from runtime.effects.
    """

    def __init__(self, cfg: OpenAICompatConfig) -> None:
        self._cfg = cfg

    def _payload_for(self, req: LLMRequest) -> Dict[str, Any]:
        model = req.model or self._cfg.default_model
        payload: Dict[str, Any] = {
            "model": model,
            "input": [
                {"role": m.role, "content": [{"type": "input_text", "text": m.content}]}
                for m in req.messages
            ],
            "temperature": req.temperature,
            "top_p": req.top_p,
            "max_output_tokens": req.max_tokens,
        }
        if req.metadata:
            payload["metadata"] = safe_metadata(req.metadata)
        return payload

    @staticmethod
    def _response_from(data: Dict[str, Any]) -> LLMResponse:
        text = _extract_text(data)
        usage = _extract_usage(data)
        finish = _extract_finish(data)
        return LLMResponse(
            content=text,
            finish_reason=finish,
            usage=usage,
            raw=(dict(data) if isinstance(data, dict) else None),
        )

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        """Synchronous generation (used by sync runtimes).

        NOTE:
        - Transport is executed in sealed runtime effects.
        - We keep this method sync to avoid asyncio.run() overhead.
        """
        if self._cfg.transport is None:
            raise RuntimeError("llm_transport_missing")

        payload = self._payload_for(req)
        timeout_s = int(max(3.0, float(req.timeout_s)))
        data = self._cfg.transport(self._cfg.base_url, self._cfg.api_key, payload, timeout_s)
        return self._response_from(data)

    async def generate(self, req: LLMRequest) -> LLMResponse:
        if self._cfg.transport is None:
            raise RuntimeError("llm_transport_missing")

        payload = self._payload_for(req)
        timeout_s = int(max(3.0, float(req.timeout_s)))
        data = await asyncio.to_thread(self._cfg.transport, self._cfg.base_url, self._cfg.api_key, payload, timeout_s)
        return self._response_from(data)


def _extract_text(data: Dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str) and data["output_text"].strip():
        return data["output_text"].strip()
    out = data.get("output")
    if isinstance(out, list):
        parts = []
        for item in out:
            for c in (item.get("content", []) or []):
                if isinstance(c, dict) and c.get("type") in {"output_text", "text"}:
                    t = c.get("text")
                    if isinstance(t, str) and t.strip():
                        parts.append(t.strip())
        if parts:
            return "\n".join(parts).strip()
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") or {}
        if isinstance(msg.get("content"), str):
            return msg["content"].strip()
    return ""


def _extract_usage(data: Dict[str, Any]) -> Optional[LLMUsage]:
    u = data.get("usage")
    if not isinstance(u, dict):
        return None
    pt = int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
    ct = int(u.get("completion_tokens") or u.get("output_tokens") or 0)
    tt = int(u.get("total_tokens") or (pt + ct) or 0)
    return LLMUsage(prompt_tokens=pt, completion_tokens=ct, total_tokens=tt)


def _extract_finish(data: Dict[str, Any]) -> str:
    if isinstance(data.get("finish_reason"), str):
        return data["finish_reason"]
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        fr = choices[0].get("finish_reason")
        if isinstance(fr, str):
            return fr
    return "stop"

__all__ = [
    "OpenAICompatTransport",
    "OpenAICompatConfig",
    "OpenAICompatClient",
]
