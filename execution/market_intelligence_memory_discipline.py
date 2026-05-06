from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping


CANON_MARKET_INTELLIGENCE_MEMORY_DISCIPLINE = True


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_dt(value: object) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None


@dataclass(frozen=True)
class MemoryDisciplineVerdict:
    freshness_score: float
    should_promote: bool
    should_demote: bool
    contradiction_detected: bool
    retention_until: str


@dataclass(frozen=True)
class MarketIntelligenceMemoryDiscipline:
    freshness_window_days: int = 14
    stale_after_days: int = 60
    retention_days: int = 180
    repeated_signal_threshold: int = 3

    def evaluate(self, *, signal: Mapping[str, Any], prior_signals: list[Mapping[str, Any]]) -> MemoryDisciplineVerdict:
        observed_at = _parse_dt(signal.get('observed_at') or signal.get('updated_at') or signal.get('published_at')) or _utc_now()
        age_days = max(0.0, (_utc_now() - observed_at).total_seconds() / 86400.0)
        freshness_score = 1.0 if age_days <= self.freshness_window_days else max(0.0, 1.0 - (age_days / max(1, self.stale_after_days)))
        repeated_count = self._repeated_count(signal=signal, prior_signals=prior_signals)
        contradiction = self._detect_contradiction(signal=signal, prior_signals=prior_signals)
        should_promote = freshness_score >= 0.5 and repeated_count >= self.repeated_signal_threshold and not contradiction
        should_demote = age_days >= self.stale_after_days or contradiction
        retention_until = (_utc_now() + timedelta(days=self.retention_days)).isoformat()
        return MemoryDisciplineVerdict(freshness_score=round(freshness_score, 4), should_promote=should_promote, should_demote=should_demote, contradiction_detected=contradiction, retention_until=retention_until)

    def compact(self, *, signals: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for row in sorted(signals, key=lambda x: str(x.get('observed_at') or ''), reverse=True):
            key = (str(row.get('provider') or '').strip(), str(row.get('source_family') or '').strip(), str(row.get('external_id') or '').strip())
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(row))
        return out

    def _repeated_count(self, *, signal: Mapping[str, Any], prior_signals: list[Mapping[str, Any]]) -> int:
        title = str(signal.get('title') or '').strip().lower()
        external_id = str(signal.get('external_id') or '').strip()
        count = 1
        for row in prior_signals:
            if row is signal:
                continue
            same_title = str(row.get('title') or '').strip().lower() == title and title
            same_external_id = str(row.get('external_id') or '').strip() == external_id and external_id
            if same_title or same_external_id:
                count += 1
        return count

    def _detect_contradiction(self, *, signal: Mapping[str, Any], prior_signals: list[Mapping[str, Any]]) -> bool:
        current_url = str(signal.get('url') or '').strip().lower()
        current_title = str(signal.get('title') or '').strip().lower()
        for row in prior_signals:
            if row is signal:
                continue
            if str(row.get('title') or '').strip().lower() == current_title and current_title:
                old_url = str(row.get('url') or '').strip().lower()
                if current_url and old_url and current_url != old_url:
                    return True
        return False
