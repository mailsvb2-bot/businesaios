from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit


CANON_MARKET_INTELLIGENCE_DATA_QUALITY = True

_SPAM_RE = re.compile(r'(.)\1{5,}')
_WHITESPACE_RE = re.compile(r'\s+')


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _fingerprint(row: Mapping[str, Any]) -> str:
    basis = '|'.join(str(row.get(key) or '').strip() for key in ('record_id', 'external_id', 'id', 'url', 'title', 'provider', 'source_family'))
    if not basis.strip('|'):
        basis = repr(sorted(dict(row).items()))
    return hashlib.sha256(basis.encode('utf-8', errors='replace')).hexdigest()


def _clean_text(value: object) -> str:
    return _WHITESPACE_RE.sub(' ', str(value or '').strip())


def _normalize_url(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ''
    parts = urlsplit(text)
    if parts.scheme.lower() not in {'http', 'https'} or not parts.netloc:
        return text
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '', parts.query, ''))


@dataclass(frozen=True)
class DataQualityReport:
    total_rows: int
    kept_rows: int
    dropped_duplicates: int
    dropped_noise: int
    anomaly_rows: int

    def as_dict(self) -> dict[str, int]:
        return {
            'total_rows': self.total_rows,
            'kept_rows': self.kept_rows,
            'dropped_duplicates': self.dropped_duplicates,
            'dropped_noise': self.dropped_noise,
            'anomaly_rows': self.anomaly_rows,
        }


class DataQualityGuard:
    def process(self, rows: Iterable[Mapping[str, Any]]) -> tuple[tuple[dict[str, Any], ...], DataQualityReport]:
        seen: set[str] = set()
        kept: list[dict[str, Any]] = []
        duplicate_count = 0
        noise_count = 0
        anomaly_count = 0
        total = 0
        for row in rows:
            total += 1
            candidate = self._normalize(_safe_dict(row))
            if self._is_noise(candidate):
                noise_count += 1
                continue
            fp = _fingerprint(candidate)
            if fp in seen:
                duplicate_count += 1
                continue
            seen.add(fp)
            if self._is_anomaly(candidate):
                candidate['quality_flag'] = 'anomaly'
                anomaly_count += 1
            kept.append(candidate)
        report = DataQualityReport(total_rows=total, kept_rows=len(kept), dropped_duplicates=duplicate_count, dropped_noise=noise_count, anomaly_rows=anomaly_count)
        return tuple(kept), report

    def _normalize(self, row: Mapping[str, Any]) -> dict[str, Any]:
        normalized = {str(key): value for key, value in dict(row).items()}
        for key in ('title', 'name', 'headline', 'description', 'copy', 'provider', 'source_family', 'record_id', 'external_id', 'id'):
            if key in normalized:
                normalized[key] = _clean_text(normalized[key])
        if 'url' in normalized:
            normalized['url'] = _normalize_url(normalized['url'])
        if 'rating' in normalized:
            try:
                normalized['rating'] = max(0.0, min(float(normalized['rating']), 5.0))
            except (TypeError, ValueError):
                pass
        for key in ('price', 'engagement', 'impressions'):
            if key in normalized:
                try:
                    normalized[key] = max(0.0, float(normalized[key]))
                except (TypeError, ValueError):
                    pass
        if 'review_count' in normalized:
            try:
                normalized['review_count'] = max(0, int(float(normalized['review_count'])))
            except (TypeError, ValueError):
                pass
        return normalized

    def _is_noise(self, row: Mapping[str, Any]) -> bool:
        text = ' '.join(_clean_text(row.get(key) or '') for key in ('title', 'name', 'headline', 'description', 'copy')).strip()
        if not text:
            return True
        if len(text) < 4:
            return True
        lowered = text.lower()
        if lowered in {'n/a', 'null', 'undefined'}:
            return True
        if 'http://' not in lowered and 'https://' not in lowered and lowered.count('buy now') >= 3:
            return True
        if _SPAM_RE.search(lowered):
            return True
        tokens = lowered.split()
        if tokens and len(set(tokens)) == 1 and len(tokens[0]) <= 8:
            return True
        if sum(ch.isdigit() for ch in lowered) > len(lowered) * 0.7:
            return True
        return False

    def _is_anomaly(self, row: Mapping[str, Any]) -> bool:
        numeric_values = []
        for key in ('price', 'rating', 'review_count', 'engagement', 'impressions'):
            value = row.get(key)
            if value is None:
                continue
            try:
                numeric_values.append(float(value))
            except (TypeError, ValueError):
                continue
        if not numeric_values:
            return False
        if any(not math.isfinite(value) for value in numeric_values):
            return True
        return any(abs(value) > 1_000_000 for value in numeric_values)


__all__ = ['CANON_MARKET_INTELLIGENCE_DATA_QUALITY', 'DataQualityGuard', 'DataQualityReport']
