from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.market_intelligence_derived_evidence_governance import MarketIntelligenceDerivedEvidenceGovernance
from execution.market_intelligence_memory_discipline import MarketIntelligenceMemoryDiscipline


CANON_MARKET_INTELLIGENCE_BUSINESS_MEMORY_BRIDGE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass
class MarketIntelligenceBusinessMemoryBridge:
    governance: MarketIntelligenceDerivedEvidenceGovernance = field(default_factory=MarketIntelligenceDerivedEvidenceGovernance)
    discipline: MarketIntelligenceMemoryDiscipline = field(default_factory=MarketIntelligenceMemoryDiscipline)

    def to_memory_payload(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _safe_dict(payload)
        records = [dict(row) for row in list(normalized.get('records') or [])[:25]]
        compacted = self.discipline.compact(signals=records)
        promoted: list[dict[str, Any]] = []
        for row in compacted:
            verdict = self.discipline.evaluate(signal=row, prior_signals=compacted)
            if verdict.should_promote:
                promoted.append(
                    {
                        'external_id': str(row.get('external_id') or '').strip(),
                        'title': str(row.get('title') or '').strip(),
                        'url': row.get('url'),
                        'price': row.get('price'),
                        'rating': row.get('rating'),
                        'freshness_score': verdict.freshness_score,
                        'retention_until': verdict.retention_until,
                    }
                )
        out: dict[str, Any] = {
            'memory_kind': 'market_intelligence',
            'memory_policy_controlled': True,
            'source_family': str(normalized.get('source_family') or '').strip(),
            'provider': str(normalized.get('provider') or '').strip(),
            'summary': _safe_dict(normalized.get('summary')),
            'records_count': len(records),
            'promoted_signals': promoted,
        }
        if promoted:
            derived = self.governance.build(
                tenant_id=str(normalized.get('tenant_id') or 'default'),
                derived_kind='market_signal_summary',
                confidence=0.80,
                raw_records=records,
                payload={
                    'source_family': str(normalized.get('source_family') or '').strip(),
                    'provider': str(normalized.get('provider') or '').strip(),
                    'records_count': len(records),
                    'promoted_signals': promoted,
                },
                ranking_policy_name='market_intelligence_memory_promotion_v2',
                explainability={'promoted_count': len(promoted), 'compacted_count': len(compacted), 'memory_policy': 'time_aware_memory_discipline_v1'},
            )
            out['derived_evidence'] = derived.as_dict()
        else:
            out['derived_evidence'] = None
            out['memory_note'] = 'no signals promoted by policy'
        return out


__all__ = ['CANON_MARKET_INTELLIGENCE_BUSINESS_MEMORY_BRIDGE', 'MarketIntelligenceBusinessMemoryBridge']
