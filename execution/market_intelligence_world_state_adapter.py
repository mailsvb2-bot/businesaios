from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from kernel.world_state import WorldStateV1


CANON_MARKET_INTELLIGENCE_WORLD_STATE_ADAPTER = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class MarketIntelligenceWorldStateAdapter:
    def inject(self, *, world_state: WorldStateV1, payload: Mapping[str, Any]) -> WorldStateV1:
        normalized = self.to_world_state_patch(payload)
        meta = dict(world_state.meta or {})
        intelligence = dict(meta.get('market_intelligence') or {})
        family = str(normalized.get('source_family') or '').strip() or 'unknown'
        intelligence[family] = normalized
        meta['market_intelligence'] = intelligence
        return replace(world_state, meta=meta)

    def to_world_state_patch(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _safe_dict(payload)
        derived = _safe_dict(normalized.get('derived_evidence') or {})
        return {
            'source_family': str(normalized.get('source_family') or '').strip(),
            'provider': str(normalized.get('provider') or '').strip(),
            'operation': str(normalized.get('operation') or normalized.get('action_type') or '').strip(),
            'summary': _safe_dict(normalized.get('summary') or normalized.get('policy_summary')),
            'records_count': len(list(normalized.get('records') or [])),
            'bounded_influence': {
                'planning_weight_cap': 0.20,
                'requires_evidence_verification': True,
                'derived_evidence_id': str(derived.get('evidence_id') or '').strip() or None,
            },
        }


__all__ = ['CANON_MARKET_INTELLIGENCE_WORLD_STATE_ADAPTER', 'MarketIntelligenceWorldStateAdapter']
