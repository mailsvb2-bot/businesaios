from __future__ import annotations

"""Causal evidence builders from an in-memory event window.

Design goals:
- Pure functions: input is a list of already-loaded events.
- Bounded compute: O(N) with small constants.
- No external deps (no numpy/pandas/sklearn).

We build simple panel datasets by day and run tiny estimators from core.causal.
This is intentionally conservative: it is evidence, not a 'second brain'.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from collections.abc import Iterable

from core.causal.api import estimate_causal_effect
from core.causal.types import CausalDataset, CausalQuery, CausalRow, EffectEstimate

Json = dict[str, Any]


def _ts_ms(ev: Json) -> int | None:
    # Support a few common shapes.
    for k in ("timestamp_ms", "ts_ms", "time_ms", "created_at_ms"):
        v = ev.get(k)
        if v is None:
            continue
        try:
            return int(v)
        except Exception:
            continue
    # Some stores keep ISO strings; we refuse to parse to keep it dependency-free.
    return None


def _event_type(ev: Json) -> str:
    return str(ev.get("event_type") or ev.get("type") or ev.get("name") or "").strip()


def _payload(ev: Json) -> Json:
    p = ev.get("payload")
    return dict(p) if isinstance(p, dict) else {}


def _day_index(ts_ms: int) -> int:
    # UTC day index.
    return int(ts_ms) // (24 * 3600 * 1000)


def _dow(day_index: int) -> int:
    # 1970-01-01 was Thursday (dow=3 if Monday=0).
    # This is good enough for stratification.
    return int((day_index +3) % 7)


@dataclass(frozen=True)
class DailyPanel:
    rows: list[CausalRow]
    meta: Json


def build_daily_panel(
    events: Iterable[Json],
    *,
    treatment_event_types: tuple[str, ...],
    outcome_event_types: tuple[str, ...],
    revenue_minor_keys: tuple[str, ...] = ("amount_minor", "amount", "sum_minor"),
    max_days: int = 60,
) -> DailyPanel:
    """Aggregate an event window into per-day rows.

    Each row:
      - y: outcome count (or revenue minor if present)
      - t: treatment indicator (any treatment event that day)
      - x: basic covariates: dow, prev_y

    Notes:
    - We keep it strict: if timestamps are missing, events are ignored.
    - Revenue is best-effort: if any outcome event has amount_minor we sum it.
      Otherwise y is a count.
    """

    te = {str(x).strip() for x in treatment_event_types if str(x).strip()}
    oe = {str(x).strip() for x in outcome_event_types if str(x).strip()}
    if not te or not oe:
        return DailyPanel(rows=[], meta={"reason": "empty_types"})

    buckets: dict[int, dict[str, Any]] = {}

    # First pass: bucket events
    for ev in list(events):
        if not isinstance(ev, dict):
            continue
        ts = _ts_ms(ev)
        if ts is None:
            continue
        day = _day_index(ts)
        b = buckets.get(day)
        if b is None:
            b = {"t": 0, "y": 0.0, "y_is_revenue": False}
            buckets[day] = b

        et = _event_type(ev)
        if et in te:
            b["t"] = 1

        if et in oe:
            pay = _payload(ev)
            amt = None
            for k in revenue_minor_keys:
                if k in pay and pay.get(k) is not None:
                    try:
                        amt = float(pay.get(k))
                        break
                    except Exception:
                        amt = None
            if amt is not None:
                b["y"] = float(b.get("y") or 0.0) + float(amt)
                b["y_is_revenue"] = True
            else:
                # count
                b["y"] = float(b.get("y") or 0.0) + 1.0

    if not buckets:
        return DailyPanel(rows=[], meta={"reason": "no_buckets"})

    # Select last max_days days
    days = sorted(buckets.keys())
    if max_days > 0 and len(days) > int(max_days):
        days = days[-int(max_days):]

    rows: list[CausalRow] = []
    prev_y: float = 0.0
    for d in days:
        b = buckets[d]
        y = float(b.get("y") or 0.0)
        t = int(b.get("t") or 0)
        x = {"dow": _dow(d), "prev_y": float(prev_y)}
        # FIX: CausalRow requires unit_id, timestamp_ms, treatment, outcome, covariates.
        # Previous code used wrong field names (y/t/x) — this crashed at runtime with
        # TypeError since CausalRow is a frozen dataclass with no such fields.
        rows.append(
            CausalRow(
                unit_id=str(d),
                timestamp_ms=max(1, int(d) * 24 * 3600 * 1000),
                treatment=float(t),
                outcome=y,
                covariates=x,
            )
        )
        prev_y = y

    meta: Json = {
        "n_days": len(rows),
        "y_kind": "revenue_minor" if any(bool(buckets[d].get("y_is_revenue")) for d in days) else "count",
        "treatment_types": sorted(te),
        "outcome_types": sorted(oe),
        "max_days": int(max_days),
    }
    return DailyPanel(rows=rows, meta=meta)


def estimate_effect_from_daily_panel(panel: DailyPanel, *, method: str = "dr") -> CausalResult | None:  # noqa: F821
    if not panel.rows:
        return None
    # FIX: CausalDataset has no `meta` field — pass only rows.
    ds = CausalDataset(rows=list(panel.rows))
    q = CausalQuery(estimand="ATE", method=str(method or "dr"), outcome_name="outcome", treatment_name="treatment")
    # FIX: estimate_causal_effect takes `query` as keyword-only argument.
    return estimate_causal_effect(ds, query=q)


def placebo_shift_treatment(panel: DailyPanel, *, shift_days: int = 1, method: str = "dr") -> CausalResult | None:  # noqa: F821
    """Placebo test: shift treatment forward by N days.

    If we still see a strong effect after shifting, it's a warning sign.
    """
    if not panel.rows:
        return None

    s = int(shift_days)
    if s == 0:
        return estimate_effect_from_daily_panel(panel, method=method)

    rows = list(panel.rows)
    # FIX: use correct CausalRow field name `treatment` (not `t`)
    t_series = [int(r.treatment) for r in rows]
    shifted = [0] * len(t_series)
    for i, v in enumerate(t_series):
        j = i + s
        if 0 <= j < len(shifted):
            shifted[j] = int(v)

    out_rows: list[CausalRow] = []
    for i, r in enumerate(rows):
        # FIX: use correct CausalRow field names (treatment/outcome/covariates)
        out_rows.append(
            CausalRow(
                unit_id=r.unit_id,
                timestamp_ms=r.timestamp_ms,
                treatment=float(shifted[i]),
                outcome=float(r.outcome),
                covariates=dict(r.covariates or {}),
            )
        )

    # FIX: CausalDataset has no `meta` field — pass only rows.
    ds = CausalDataset(rows=out_rows)
    q = CausalQuery(estimand="ATE", method=str(method or "dr"), outcome_name="outcome", treatment_name="treatment")
    # FIX: estimate_causal_effect takes `query` as keyword-only argument.
    return estimate_causal_effect(ds, query=q)
