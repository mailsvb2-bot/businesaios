from __future__ import annotations

from datetime import UTC, datetime
from math import exp

from core.growth.attribution_models import AttributionModel, Touchpoint


def compute_weights(tps: list[Touchpoint], model: AttributionModel) -> dict[int, float]:
    if not tps:
        return {}
    if model == AttributionModel.FIRST_TOUCH:
        return {0: 1.0}
    if model == AttributionModel.LAST_TOUCH:
        return {len(tps)-1: 1.0}
    if model == AttributionModel.LINEAR:
        w=1.0/len(tps)
        return {i:w for i in range(len(tps))}
    if model == AttributionModel.TIME_DECAY:
        now=datetime.now(UTC)
        lam=0.35
        raw=[]
        for i,tp in enumerate(tps):
            ts=_parse_iso(tp.ts_iso)
            age=max(0.0,(now-ts).total_seconds()/86400.0)
            raw.append((i, exp(-lam*age)))
        s=sum(v for _,v in raw) or 1.0
        return {i:v/s for i,v in raw}
    return {len(tps)-1: 1.0}

def _parse_iso(s: str) -> datetime:
    dt=datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=UTC)
    return dt
