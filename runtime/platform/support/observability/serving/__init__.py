from __future__ import annotations

"""Canonical serving observability surface with compat alias submodules."""

class ActionDistributionMetrics:
    def summarize(self, counts: dict[str, int]) -> dict[str, int]:
        return dict(counts)

class ErrorMetrics:
    def summarize(self, errors: int) -> dict[str, int]:
        return {"errors": errors}

class FallbackMetrics:
    def summarize(self, fallbacks: int) -> dict[str, int]:
        return {"fallbacks": fallbacks}

class InferenceMetrics:
    def summarize(self, count: int) -> dict[str, int]:
        return {"inference_count": count}

class LatencyMetrics:
    def summarize(self, values_ms: list[float]) -> dict[str, float]:
        if not values_ms:
            return {"latency_ms": 0.0}
        return {"latency_ms": sum(values_ms) / len(values_ms)}

_ALIAS_EXPORTS = {
    "action_distribution_metrics": "ActionDistributionMetrics",
    "error_metrics": "ErrorMetrics",
    "fallback_metrics": "FallbackMetrics",
    "inference_metrics": "InferenceMetrics",
    "latency_metrics": "LatencyMetrics",
}

__all__ = [
    "ActionDistributionMetrics",
    "ErrorMetrics",
    "FallbackMetrics",
    "InferenceMetrics",
    "LatencyMetrics",
] + list(_ALIAS_EXPORTS)
