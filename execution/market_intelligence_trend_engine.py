from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import json
from statistics import pstdev

from execution.market_intelligence_advanced_models import TrendPoint


CANON_MARKET_INTELLIGENCE_TREND_ENGINE = True


def _safe_key(value: object) -> str:
    return ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in str(value or '').strip() or 'unknown')


def _parse_dt(value: object) -> datetime:
    text = str(value or '').strip()
    if not text:
        return datetime.min.replace(tzinfo=UTC)
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00')).astimezone(UTC)
    except ValueError:
        return datetime.min.replace(tzinfo=UTC)


@dataclass
class FileTrendStore:
    root_dir: Path = Path('.runtime_data/market_intelligence/trends')

    def append(self, point: TrendPoint) -> None:
        path = self.root_dir / _safe_key(point.tenant_id) / f'{_safe_key(point.entity_id)}__{_safe_key(point.metric)}.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({'tenant_id': point.tenant_id, 'entity_id': point.entity_id, 'metric': point.metric, 'value': point.value, 'observed_at': point.observed_at, 'metadata': dict(point.metadata)}, ensure_ascii=False) + '\n')

    def load(self, *, tenant_id: str, entity_id: str, metric: str) -> tuple[TrendPoint, ...]:
        path = self.root_dir / _safe_key(tenant_id) / f'{_safe_key(entity_id)}__{_safe_key(metric)}.jsonl'
        if not path.exists():
            return ()
        rows: list[TrendPoint] = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                try:
                    rows.append(TrendPoint(**payload))
                except Exception:
                    continue
        rows.sort(key=lambda point: _parse_dt(point.observed_at))
        return tuple(rows)


@dataclass(frozen=True)
class TrendSummary:
    entity_id: str
    metric: str
    slope: float
    volatility: float
    latest_value: float
    points: int

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            'entity_id': self.entity_id,
            'metric': self.metric,
            'slope': self.slope,
            'volatility': self.volatility,
            'latest_value': self.latest_value,
            'points': self.points,
        }


@dataclass
class TemporalTrendEngine:
    store: FileTrendStore = field(default_factory=FileTrendStore)

    def observe(self, point: TrendPoint) -> None:
        self.store.append(point)

    def summarize(self, *, tenant_id: str, entity_id: str, metric: str) -> TrendSummary:
        points = self.store.load(tenant_id=tenant_id, entity_id=entity_id, metric=metric)
        values = [float(item.value) for item in points]
        if not values:
            return TrendSummary(entity_id=entity_id, metric=metric, slope=0.0, volatility=0.0, latest_value=0.0, points=0)
        slope = 0.0 if len(values) < 2 else (values[-1] - values[0]) / max(1, len(values) - 1)
        volatility = 0.0 if len(values) < 2 else float(pstdev(values))
        return TrendSummary(entity_id=entity_id, metric=metric, slope=slope, volatility=volatility, latest_value=values[-1], points=len(values))


__all__ = ['CANON_MARKET_INTELLIGENCE_TREND_ENGINE', 'FileTrendStore', 'TemporalTrendEngine', 'TrendSummary']
