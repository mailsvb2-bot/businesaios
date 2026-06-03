from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from collections.abc import Iterable, Mapping


CANON_MARKET_INTELLIGENCE_PATTERN_EXTRACTOR = True


_PRICE_RE = re.compile(r'\b(?:\$|€|£)?\s?(\d{1,6}(?:[\.,]\d{1,2})?)\b')
_CTA_RE = re.compile(r'\b(buy now|learn more|sign up|start free|book now|get started|join now|download)\b', re.IGNORECASE)
_HEADLINE_SPLIT_RE = re.compile(r'[\n\r\|\-–—]+')


@dataclass(frozen=True)
class ExtractedPatterns:
    headlines: tuple[str, ...]
    ctas: tuple[str, ...]
    pricing_anchors: tuple[str, ...]
    offer_structures: tuple[str, ...]

    def as_dict(self) -> dict[str, list[str]]:
        return {
            'headlines': list(self.headlines),
            'ctas': list(self.ctas),
            'pricing_anchors': list(self.pricing_anchors),
            'offer_structures': list(self.offer_structures),
        }


class ContentOfferPatternExtractor:
    def extract(self, rows: Iterable[Mapping[str, object]]) -> ExtractedPatterns:
        headlines: Counter[str] = Counter()
        ctas: Counter[str] = Counter()
        prices: Counter[str] = Counter()
        structures: Counter[str] = Counter()
        for row in rows:
            text = ' '.join(str(row.get(key) or '') for key in ('headline', 'title', 'copy', 'description', 'offer'))
            for fragment in _HEADLINE_SPLIT_RE.split(text):
                clean = fragment.strip()
                if 8 <= len(clean) <= 120:
                    headlines[clean] += 1
            for match in _CTA_RE.findall(text):
                ctas[match.lower()] += 1
            for match in _PRICE_RE.findall(text):
                prices[match.replace(',', '.')] += 1
            structures[self._infer_structure(row, text)] += 1
        return ExtractedPatterns(
            headlines=tuple(item for item, _ in headlines.most_common(10)),
            ctas=tuple(item for item, _ in ctas.most_common(10)),
            pricing_anchors=tuple(item for item, _ in prices.most_common(10)),
            offer_structures=tuple(item for item, _ in structures.most_common(10)),
        )

    def _infer_structure(self, row: Mapping[str, object], text: str) -> str:
        lowered = text.lower()
        if 'free trial' in lowered or 'start free' in lowered:
            return 'free_trial_offer'
        if 'save' in lowered or 'discount' in lowered or 'off' in lowered:
            return 'discount_offer'
        if 'book' in lowered or 'consultation' in lowered:
            return 'consultation_offer'
        if 'learn' in lowered or 'guide' in lowered or 'download' in lowered:
            return 'lead_magnet_offer'
        return 'generic_offer'


__all__ = ['CANON_MARKET_INTELLIGENCE_PATTERN_EXTRACTOR', 'ContentOfferPatternExtractor', 'ExtractedPatterns']
