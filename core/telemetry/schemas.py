from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.telemetry_event_policy import DEFAULT_TELEMETRY_EVENT_POLICY


@dataclass(frozen=True)
class LLMTrace:
    tenant_id: str
    user_id: str
    channel: str
    locale: str
    kind: str
    model: str
    provider: str
    request_id: str
    correlation_id: str = ""
    message_id: str = ""
    offer_id: str = ""
    experiment: str = ""
    variant: str = ""
    prompt_version: str = ""
    prompt_hash: str = ""
    cache_hit: bool = False
    latency_ms: int = DEFAULT_TELEMETRY_EVENT_POLICY.default_latency_ms
    finish_reason: str = ""
    prompt_tokens: int = DEFAULT_TELEMETRY_EVENT_POLICY.default_prompt_tokens
    completion_tokens: int = DEFAULT_TELEMETRY_EVENT_POLICY.default_completion_tokens
    total_tokens: int = DEFAULT_TELEMETRY_EVENT_POLICY.default_total_tokens
    ok: bool = True
    error_code: str = ""

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "channel": self.channel,
            "locale": self.locale,
            "kind": self.kind,
            "model": self.model,
            "provider": self.provider,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "message_id": self.message_id,
            "offer_id": self.offer_id,
            "experiment": self.experiment,
            "variant": self.variant,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "cache_hit": bool(self.cache_hit),
            "latency_ms": int(self.latency_ms),
            "finish_reason": self.finish_reason,
            "prompt_tokens": int(self.prompt_tokens),
            "completion_tokens": int(self.completion_tokens),
            "total_tokens": int(self.total_tokens),
            "ok": bool(self.ok),
            "error_code": self.error_code,
        }


@dataclass(frozen=True)
class FunnelEvent:
    """Minimal funnel payload (safe)."""

    tenant_id: str
    user_id: str
    correlation_id: str
    offer_id: str
    channel: str = DEFAULT_TELEMETRY_EVENT_POLICY.default_channel
    locale: str = DEFAULT_TELEMETRY_EVENT_POLICY.default_locale
    experiment: str = ""
    variant: str = ""
    price: float = DEFAULT_TELEMETRY_EVENT_POLICY.default_price
    currency: str = ""
    meta: dict[str, Any] | None = None

    def to_event_payload(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "offer_id": self.offer_id,
            "channel": self.channel,
            "locale": self.locale,
            "experiment": self.experiment,
            "variant": self.variant,
            "price": float(self.price or DEFAULT_TELEMETRY_EVENT_POLICY.default_price),
            "currency": self.currency,
        }
        if isinstance(self.meta, dict) and self.meta:
            d["meta"] = {k: v for k, v in self.meta.items() if isinstance(v, str | int | float | bool)}
        return d
