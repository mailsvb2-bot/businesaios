from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict

from config.final_hidden_logic_policy import DEFAULT_ANTHROPIC_PROVIDER_POLICY
from core.llm.contracts import LLMClient, LLMMessage, LLMRequest, LLMResponse, LLMUsage

AnthropicTransport = Callable[[str, str, dict[str, Any], int], dict[str, Any]]


@dataclass(frozen=True)
class AnthropicClient(LLMClient):
    """Anthropic Messages API client (pure, transport-injected)."""

    transport: AnthropicTransport
    base_url: str
    api_key: str
    model: str
    anthropic_version: str = DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_version
    timeout_s: int = DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_timeout_s

    def generate_sync(self, req: LLMRequest) -> LLMResponse:
        model = str(req.model or "").strip() or self.model
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": int(req.max_tokens or DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_max_tokens),
            "temperature": float(req.temperature or DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_temperature),
            "messages": _anthropic_messages(req.messages),
            "system": _system_prompt(req.messages),
            "_headers": {
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
                "Content-Type": "application/json",
            },
        }
        raw = self.transport(
            str(self.base_url).rstrip("/") + DEFAULT_ANTHROPIC_PROVIDER_POLICY.messages_path_suffix,
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


def _system_prompt(messages: list[LLMMessage]) -> str:
    for message in messages:
        if message.role == "system":
            return str(message.content or DEFAULT_ANTHROPIC_PROVIDER_POLICY.empty_content)[: DEFAULT_ANTHROPIC_PROVIDER_POLICY.content_preview_limit]
    return DEFAULT_ANTHROPIC_PROVIDER_POLICY.empty_content


def _anthropic_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            continue
        out.append({"role": message.role, "content": str(message.content or DEFAULT_ANTHROPIC_PROVIDER_POLICY.empty_content)[: DEFAULT_ANTHROPIC_PROVIDER_POLICY.content_preview_limit]})
    return out or [{"role": DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_user_role, "content": DEFAULT_ANTHROPIC_PROVIDER_POLICY.empty_content}]


def _extract_text(raw: dict[str, Any]) -> str:
    parts = raw.get("content") or []
    if isinstance(parts, list):
        texts: list[str] = []
        for part in parts:
            if isinstance(part, dict):
                text = str(part.get("text") or DEFAULT_ANTHROPIC_PROVIDER_POLICY.empty_content).strip()
                if text:
                    texts.append(text)
        if texts:
            return "\n".join(texts).strip()
    return str(raw.get("output_text") or DEFAULT_ANTHROPIC_PROVIDER_POLICY.empty_content).strip()


def _extract_usage(raw: dict[str, Any]) -> LLMUsage | None:
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        return None
    pt = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
    ct = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
    tt = int(usage.get("total_tokens") or (pt + ct) or 0)
    return LLMUsage(prompt_tokens=pt, completion_tokens=ct, total_tokens=tt)


def _extract_finish(raw: dict[str, Any]) -> str:
    return str(raw.get("stop_reason") or raw.get("finish_reason") or DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_stop_reason)


def build_anthropic(*, transport: AnthropicTransport, base_url: str, api_key: str, model: str, anthropic_version: str | None = None, timeout_s: int = DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_timeout_s) -> AnthropicClient:
    return AnthropicClient(
        transport=transport,
        base_url=str(base_url).strip().rstrip("/"),
        api_key=str(api_key).strip(),
        model=str(model).strip(),
        anthropic_version=str(anthropic_version or DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_version).strip() or DEFAULT_ANTHROPIC_PROVIDER_POLICY.default_version,
        timeout_s=int(timeout_s),
    )
