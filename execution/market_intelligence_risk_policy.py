from __future__ import annotations

from dataclasses import dataclass, field

from execution.market_intelligence_models import MarketIntelligenceIngestionRequest


CANON_MARKET_INTELLIGENCE_RISK_POLICY = True


@dataclass(frozen=True)
class MarketIntelligenceRiskPolicy:
    high_risk_families: tuple[str, ...] = field(default_factory=lambda: ('ads_library', 'ads_spy'))
    restricted_subject_required_families: tuple[str, ...] = field(default_factory=lambda: ('landing_intelligence', 'video_platform'))
    high_risk_limit_threshold: int = 50

    def assess(self, request: MarketIntelligenceIngestionRequest) -> dict[str, object]:
        reasons: list[str] = []
        if request.source_family in set(self.high_risk_families):
            reasons.append('high_risk_family')
        if int(request.limit) > int(self.high_risk_limit_threshold):
            reasons.append('high_limit')
        if request.source_family in set(self.restricted_subject_required_families) and not (request.subject_url or request.query):
            reasons.append('missing_subject')
        if request.dry_run:
            return {
                'risk_level': 'dry_run',
                'reasons': tuple(reasons),
                'requires_approval': False,
            }
        level = 'high' if reasons else 'normal'
        return {
            'risk_level': level,
            'reasons': tuple(reasons),
            'requires_approval': bool(reasons),
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_RISK_POLICY', 'MarketIntelligenceRiskPolicy']
