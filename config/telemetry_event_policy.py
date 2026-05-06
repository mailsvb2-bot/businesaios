from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryEventPolicy:
    default_channel: str = "telegram"
    default_locale: str = "ru"
    default_price: float = 0.0
    default_latency_ms: int = 0
    default_prompt_tokens: int = 0
    default_completion_tokens: int = 0
    default_total_tokens: int = 0


DEFAULT_TELEMETRY_EVENT_POLICY = TelemetryEventPolicy()


__all__ = ["TelemetryEventPolicy", "DEFAULT_TELEMETRY_EVENT_POLICY"]
