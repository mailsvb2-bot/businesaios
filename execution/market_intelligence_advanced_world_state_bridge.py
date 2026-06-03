from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable

from contracts.platforms.market_intelligence_advanced_contract import OpportunityEvidence, UnifiedSignal


CANON_MARKET_INTELLIGENCE_ADVANCED_WORLD_STATE_BRIDGE = True


@dataclass
class AdvancedWorldStateBridge:
    def build_patch(self, *, signals: Iterable[UnifiedSignal], opportunities: Iterable[OpportunityEvidence], trend_summaries: Iterable[dict[str, Any]]) -> dict[str, Any]:
        signal_rows = [item.as_dict() for item in signals]
        opportunity_rows = [item.as_dict() for item in opportunities]
        trend_rows = [dict(item) for item in trend_summaries]
        return {
            'market_intelligence_advanced': {
                'latest_signals': signal_rows[:50],
                'latest_opportunities': opportunity_rows[:25],
                'trend_summaries': trend_rows[:25],
                'signals_count': len(signal_rows),
                'opportunities_count': len(opportunity_rows),
            }
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_ADVANCED_WORLD_STATE_BRIDGE', 'AdvancedWorldStateBridge']
