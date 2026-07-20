from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

CANON_MARKET_INTELLIGENCE_DATA_QUALITY = True

_SPAM_RE = re.compile(r"(.)\1{5,}")
_WHITESPACE_RE = re.compile(r"\s+")


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _fingerprint(row: Mapping[str, Any]) -> str:
    identity = tuple(
        str(row.get(key) or "").strip()
        for key in (
            "record_id",
            "external_id",
            "id",
            "url",
            "title",
            "provider",
            "source_family",
        )
    )
    if any(identity):
        basis = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
    else:
        basis = repr(sorted(dict(row).items()))
    return hashlib.sha256(basis.encode("utf-8", errors="replace")).hexdigest()


def _clean_text(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip())


def _normalize_url(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    parts = urlsplit(text)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        return text
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "",
            parts.query,
            "",
        )
    )


def _normalized_float(value: object, *, upper: float | None = None) -> object:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(parsed):
        return parsed
    normalized = max(0.0, parsed)
    return min(normalized, upper) if upper is not None else normalized


def _normalized_int(value: object) -> object:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(parsed):
        return parsed
    return max(0, int(parsed))


@dataclass(frozen=True)
class DataQualityReport:
    total_rows: int
    kept_rows: int
    dropped_duplicates: int
    dropped_noise: int
    anomaly_rows: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total_rows": self.total_rows,
            "kept_rows": self.kept_rows,
            "dropped_duplicates": self.dropped_duplicates,
            "dropped_noise": self.dropped_noise,
            "anomaly_rows": self.anomaly_rows,
        }


class DataQualityGuard:
    def process(
        self,
        rows: Iterable[Mapping[str, Any]],
    ) -> tuple[tuple[dict[str, Any], ...], DataQualityReport]:
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
                candidate["quality_flag"] = "anomaly"
                anomaly_count += 1
            kept.append(candidate)
        report = DataQualityReport(
            total_rows=total,
            kept_rows=len(kept),
            dropped_duplicates=duplicate_count,
            dropped_noise=noise_count,
            anomaly_rows=anomaly_count,
        )
        return tuple(kept), report

    def _normalize(self, row: Mapping[str, Any]) -> dict[str, Any]:
        normalized = {str(key): value for key, value in dict(row).items()}
        for key in (
            "title",
            "name",
            "headline",
            "description",
            "copy",
            "provider",
            "source_family",
            "record_id",
            "external_id",
            "id",
        ):
            if key in normalized:
                normalized[key] = _clean_text(normalized[key])
        if "url" in normalized:
            normalized["url"] = _normalize_url(normalized["url"])
        if "rating" in normalized:
            normalized["rating"] = _normalized_float(normalized["rating"], upper=5.0)
        for key in ("price", "engagement", "impressions"):
            if key in normalized:
                normalized[key] = _normalized_float(normalized[key])
        if "review_count" in normalized:
            normalized["review_count"] = _normalized_int(normalized["review_count"])
        return normalized

    def _is_noise(self, row: Mapping[str, Any]) -> bool:
        text = " ".join(
            _clean_text(row.get(key) or "")
            for key in (
                "title",
                "name",
                "headline",
                "description",
                "copy",
            )
        ).strip()
        if not text or len(text) < 4:
            return True
        lowered = text.lower()
        if lowered in {"n/a", "null", "undefined"}:
            return True
        if (
            "http://" not in lowered
            and "https://" not in lowered
            and lowered.count("buy now") >= 3
        ):
            return True
        if _SPAM_RE.search(lowered):
            return True
        tokens = lowered.split()
        if tokens and len(set(tokens)) == 1 and len(tokens[0]) <= 8:
            return True
        return sum(ch.isdigit() for ch in lowered) > len(lowered) * 0.7

    def _is_anomaly(self, row: Mapping[str, Any]) -> bool:
        numeric_values: list[float] = []
        for key in (
            "price",
            "rating",
            "review_count",
            "engagement",
            "impressions",
        ):
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


__all__ = [
    "CANON_MARKET_INTELLIGENCE_DATA_QUALITY",
    "DataQualityGuard",
    "DataQualityReport",
]
