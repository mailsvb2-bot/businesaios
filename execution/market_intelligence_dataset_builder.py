from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from execution.market_intelligence_models import MarketIntelligenceDatasetRow


CANON_MARKET_INTELLIGENCE_DATASET_BUILDER = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


@dataclass(frozen=True)
class MarketIntelligenceDatasetBuilder:
    def build_rows(self, payload: Mapping[str, Any]) -> tuple[MarketIntelligenceDatasetRow, ...]:
        normalized = _safe_dict(payload)
        rows: list[MarketIntelligenceDatasetRow] = []
        for item in normalized.get('records') or []:
            record = _safe_dict(item)
            text = ' | '.join(
                token for token in [
                    str(record.get('title') or '').strip(),
                    str(record.get('body') or '').strip(),
                    str(record.get('url') or '').strip(),
                ]
                if token
            )
            rows.append(
                MarketIntelligenceDatasetRow(
                    source_family=str(normalized.get('source_family') or '').strip(),
                    provider=str(normalized.get('provider') or '').strip(),
                    record_id=str(record.get('external_id') or '').strip() or f"row:{len(rows)}",
                    text=text,
                    features={
                        'price': record.get('price'),
                        'rating': record.get('rating'),
                        'tags': list(record.get('tags') or []),
                    },
                )
            )
        return tuple(rows)


__all__ = ['CANON_MARKET_INTELLIGENCE_DATASET_BUILDER', 'MarketIntelligenceDatasetBuilder']
