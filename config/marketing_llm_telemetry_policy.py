from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketingLLMTelemetryPolicy:
    zero_error_rate: float = 0.0
    alert_p95_latency_ms: int = 2500
    alert_error_rate: float = 0.25
    alert_min_total: int = 20
    debug_sample_event_type: str = "llm_debug_sample"


DEFAULT_MARKETING_LLM_TELEMETRY_POLICY = MarketingLLMTelemetryPolicy()
