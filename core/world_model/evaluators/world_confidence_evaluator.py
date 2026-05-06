from __future__ import annotations

from core.world_model.enums import SignalFreshness
from core.world_model.types import CompletenessReport, ConfidenceReport, FreshnessReport


class WorldConfidenceEvaluator:
    def evaluate(self, *, freshness: FreshnessReport, completeness: CompletenessReport) -> ConfidenceReport:
        freshness_score = self._freshness_score(freshness)
        completeness_score = float(completeness.score)
        total = (freshness_score * 0.55) + (completeness_score * 0.45)
        reasons = []
        if freshness.worst_status == SignalFreshness.MISSING:
            reasons.append("missing_signals_present")
        elif freshness.worst_status == SignalFreshness.STALE:
            reasons.append("stale_signals_present")
        if completeness.missing_fields:
            reasons.append("required_fields_missing")
        if not reasons:
            reasons.append("state_is_actionable_for_read_only_context")
        return ConfidenceReport(score=float(round(total, 4)), freshness_weight=0.55, completeness_weight=0.45, reasons=tuple(reasons))

    def _freshness_score(self, freshness: FreshnessReport) -> float:
        values = list(freshness.per_reader.values())
        if not values:
            return 0.0
        total = 0.0
        for item in values:
            if item == SignalFreshness.FRESH:
                total += 1.0
            elif item == SignalFreshness.STALE:
                total += 0.4
            else:
                total += 0.0
        return total / float(len(values))
