from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CANON_MARKET_INTELLIGENCE_NORMALIZER = True


@dataclass(frozen=True)
class MarketIntelligenceRecordNormalizer:
    max_text_len: int = 5000
    max_title_len: int = 500
    max_metadata_items: int = 24
    max_scalar_value_len: int = 500

    def normalize_record(self, record: Mapping[str, Any]) -> dict[str, Any]:
        normalized = dict(record or {})
        normalized['provider'] = str(normalized.get('provider') or '').strip()
        normalized['source_family'] = str(normalized.get('source_family') or '').strip()
        normalized['external_id'] = str(normalized.get('external_id') or '').strip()
        normalized['title'] = self._clean_text(normalized.get('title'), limit=self.max_title_len)
        normalized['body'] = self._clean_text(normalized.get('body'), limit=self.max_text_len)
        normalized['url'] = self._clean_url(normalized.get('url'))
        price = self._safe_float(normalized.get('price'))
        normalized['price'] = price if price is None else max(0.0, price)
        rating = self._safe_float(normalized.get('rating'))
        normalized['rating'] = None if rating is None else max(0.0, min(5.0, rating))
        review_count = self._safe_int(normalized.get('review_count'))
        normalized['review_count'] = None if review_count is None else max(0, review_count)
        engagement = normalized.get('engagement')
        normalized['engagement'] = self._sanitize_mapping(engagement) if isinstance(engagement, Mapping) else {}
        evidence = normalized.get('evidence')
        metadata = normalized.get('metadata')
        normalized['evidence'] = self._sanitize_mapping(evidence) if isinstance(evidence, Mapping) else {}
        normalized['metadata'] = self._sanitize_mapping(metadata) if isinstance(metadata, Mapping) else {}
        tags = normalized.get('tags') or ()
        normalized['tags'] = tuple(sorted({str(item).strip().lower() for item in tags if str(item).strip()}))
        dedup_hint = str(normalized.get('external_id') or normalized.get('url') or normalized.get('title') or '').strip().lower()
        normalized['dedup_hint'] = dedup_hint
        return normalized

    def _clean_text(self, value: object, *, limit: int) -> str:
        text = ' '.join(str(value or '').split())
        return text[:limit]

    def _clean_url(self, value: object) -> str | None:
        text = str(value or '').strip()
        if not text:
            return None
        if text.startswith(('http://', 'https://')):
            return text[:2048]
        return None

    def _sanitize_mapping(self, value: Mapping[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(dict(value or {}).items()):
            if index >= int(self.max_metadata_items):
                break
            clean_key = str(key).strip()[:120]
            if not clean_key:
                continue
            if isinstance(item, Mapping):
                out[clean_key] = {
                    str(nested_key).strip()[:120]: self._sanitize_scalar(nested_value)
                    for nested_key, nested_value in list(dict(item).items())[:8]
                    if str(nested_key).strip()
                }
            elif isinstance(item, (list, tuple, set)):
                out[clean_key] = [self._sanitize_scalar(entry) for entry in list(item)[:12]]
            else:
                out[clean_key] = self._sanitize_scalar(item)
        return out

    def _sanitize_scalar(self, value: Any) -> Any:
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return str(value).strip()[: self.max_scalar_value_len]

    def _safe_float(self, value: object) -> float | None:
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _safe_int(self, value: object) -> int | None:
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


__all__ = ['CANON_MARKET_INTELLIGENCE_NORMALIZER', 'MarketIntelligenceRecordNormalizer']
