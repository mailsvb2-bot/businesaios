from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..contracts import LLMClient, LLMMessage, LLMRequest, LLMResponse, LLMUsage
from ..redaction import safe_metadata

YandexGPTTransport = Callable[[str, str, dict[str, Any], int], dict[str, Any]]


@dataclass(frozen=True)
class YandexGPTClient(LLMClient):
    transport: YandexGPTTransport
    base_url: str
    api_key: str
    model: str = "yandexgpt-lite"
    timeout_s: int = 20

    def _payload(self, req: LLMRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "modelUri": self.model,
            "completionOptions": {
                "stream": False,
                "temperature": float(req.temperature),
                "maxTokens": int(req.max_tokens),
            },
            "messages": _messages(req.messages),
        }
        if req.metadata:
            payload["metadata"] = safe_metadata(req.metadata)
        return payload

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        raw = self.transport(self.base_url, self.api_key, self._payload(req), int(req.timeout_s or self.timeout_s))
        return LLMResponse(
            content=_extract_text(raw),
            finish_reason=_extract_finish(raw),
            usage=_extract_usage(raw),
            raw=(dict(raw) if isinstance(raw, dict) else None),
        )

    async def generate(self, req: LLMRequest) -> LLMResponse:
        import asyncio

        return await asyncio.to_thread(self.generate_sync, req)


def _messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        out.append({"role": message.role, "text": str(message.content or "")[:8000]})
    return out or [{"role": "user", "text": ""}]


def _extract_text(raw: dict[str, Any]) -> str:
    result = raw.get("result")
    if not isinstance(result, dict):
        return ""
    alts = result.get("alternatives") or []
    if not isinstance(alts, list) or not alts:
        return ""
    first = alts[0] or {}
    if not isinstance(first, dict):
        return ""
    msg = first.get("message") or {}
    if not isinstance(msg, dict):
        return ""
    return str(msg.get("text") or "").strip()


def _extract_usage(raw: dict[str, Any]) -> LLMUsage | None:
    usage = (raw.get("result") or {}).get("usage") if isinstance(raw.get("result"), dict) else raw.get("usage")
    if not isinstance(usage, dict):
        return None
    pt = int(usage.get("inputTextTokens") or usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    ct = int(usage.get("completionTokens") or usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    tt = int(usage.get("totalTokens") or usage.get("total_tokens") or (pt + ct) or 0)
    return LLMUsage(prompt_tokens=pt, completion_tokens=ct, total_tokens=tt)


def _extract_finish(raw: dict[str, Any]) -> str:
    result = raw.get("result")
    if isinstance(result, dict) and result.get("finishReason") is not None:
        return str(result.get("finishReason"))
    return str(raw.get("finish_reason") or "stop")


def build_yandexgpt(*, transport: YandexGPTTransport, base_url: str, api_key: str, model: str, timeout_s: int = 20) -> YandexGPTClient:
    return YandexGPTClient(
        transport=transport,
        base_url=str(base_url).strip(),
        api_key=str(api_key).strip(),
        model=str(model).strip(),
        timeout_s=int(timeout_s),
    )
