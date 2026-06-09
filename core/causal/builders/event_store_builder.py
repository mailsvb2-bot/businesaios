from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable, Mapping, Sequence

from config.final_hidden_logic_policy import DEFAULT_CAUSAL_BUILDER_POLICY
from core.causal.types import CausalDataset, CausalRow

Json = dict[str, Any]


def _now_ms() -> int:
    return int(time.time() * DEFAULT_CAUSAL_BUILDER_POLICY.milliseconds_per_second)


def _require_tenant_id(tenant_id: str) -> str:
    tid = str(tenant_id or "").strip()
    if not tid:
        raise ValueError("tenant_id is required (strict)")
    return tid


def _iter_events_compat(
    event_store: Any,
    *,
    tenant_id: str,
    event_type: str,
    start_ms: int,
    end_ms: int,
) -> Iterable[Mapping[str, Any]]:
    """Iterate events across different event_store backends.

    Project has both query(...) and iter_events(...). Prefer iter_events when present.
    """

    if hasattr(event_store, "iter_events"):
        return event_store.iter_events(tenant_id=tenant_id, start_ms=int(start_ms), end_ms=int(end_ms), event_type=event_type)

    # Fallback: query
    if hasattr(event_store, "query"):
        since_ms = int(start_ms)
        out = []
        while True:
            batch = event_store.query(event_type=event_type, since_ms=since_ms, limit=5000, tenant_id=tenant_id)
            if not batch:
                break
            out.extend(batch)
            # naive pagination by timestamp
            since_ms = int(max(int(e.get("timestamp_ms") or DEFAULT_CAUSAL_BUILDER_POLICY.zero_timestamp) for e in batch) + DEFAULT_CAUSAL_BUILDER_POLICY.pagination_step_ms)
            if since_ms > int(end_ms):
                break
        return out

    raise TypeError("event_store does not support iter_events/query")


@dataclass(frozen=True)
class EventCausalBuilder:
    """Build causal datasets from event store.

    This builder is intentionally simple and deterministic. It supports:

1) Binary treatment defined by the presence of treatment_event within a window.
2) Outcome as numeric extracted from outcome_event payload.

    Use cases:
    - Pricing: treatment_event=pricing_change_applied, outcome_event=payment_captured
    - Ads: treatment_event=ads_plan_applied, outcome_event=ads_metrics_imported (or payment_captured)

    Rows are produced per unit_id (user_id by default).
    """

    unit_id_key: str = "user_id"

    def build_binary_treatment_dataset(
        self,
        event_store: Any,
        *,
        tenant_id: str,
        treatment_event: str,
        outcome_event: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        outcome_value_path: tuple[str, ...] = ("payload", "amount"),
        covariate_extractors: Sequence[tuple[str, tuple[str, ...]]] = (),
        max_events: int = DEFAULT_CAUSAL_BUILDER_POLICY.binary_dataset_max_events,
    ) -> CausalDataset:
        tid = _require_tenant_id(tenant_id)
        end = int(end_ms or _now_ms())
        start = int(start_ms or (end - DEFAULT_CAUSAL_BUILDER_POLICY.default_lookback_days * DEFAULT_CAUSAL_BUILDER_POLICY.seconds_per_day * DEFAULT_CAUSAL_BUILDER_POLICY.milliseconds_per_second))

        # Collect treatment assignments (unit_id -> earliest treatment ts)
        treated_at: dict[str, int] = {}
        for ev in _iter_events_compat(event_store, tenant_id=tid, event_type=str(treatment_event), start_ms=start, end_ms=end):
            uid = str(ev.get(self.unit_id_key) or "").strip()
            if not uid:
                continue
            ts = int(ev.get("timestamp_ms") or DEFAULT_CAUSAL_BUILDER_POLICY.zero_timestamp)
            if ts <= DEFAULT_CAUSAL_BUILDER_POLICY.zero_timestamp:
                continue
            prev = treated_at.get(uid)
            if prev is None or ts < prev:
                treated_at[uid] = ts
            if len(treated_at) >= int(max_events):
                break

        # Build outcome rows per unit. For robustness, we aggregate outcomes per unit over the window.
        out_sum: dict[str, float] = {}
        out_ts: dict[str, int] = {}
        covs: dict[str, dict[str, Any]] = {}

        def _get_path(d: Mapping[str, Any], path: tuple[str, ...]) -> Any:
            cur: Any = d
            for p in path:
                if not isinstance(cur, Mapping):
                    return None
                cur = cur.get(p)
            return cur

        for ev in _iter_events_compat(event_store, tenant_id=tid, event_type=str(outcome_event), start_ms=start, end_ms=end):
            uid = str(ev.get(self.unit_id_key) or "").strip()
            if not uid:
                continue
            ts = int(ev.get("timestamp_ms") or DEFAULT_CAUSAL_BUILDER_POLICY.zero_timestamp)
            if ts <= DEFAULT_CAUSAL_BUILDER_POLICY.zero_timestamp:
                continue
            v = _get_path(ev, outcome_value_path)
            try:
                vf = float(v or DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value)
            except Exception:
                vf = DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value
            out_sum[uid] = float(out_sum.get(uid, DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value)) + float(vf)
            out_ts[uid] = max(int(out_ts.get(uid, DEFAULT_CAUSAL_BUILDER_POLICY.zero_timestamp)), ts)

            if covariate_extractors and uid not in covs:
                cov: dict[str, Any] = {}
                for name, pth in covariate_extractors:
                    cov[name] = _get_path(ev, pth)
                covs[uid] = cov

            if len(out_sum) >= int(max_events):
                break

        # Union of units.
        units = set(out_sum.keys()) | set(treated_at.keys())
        rows: list[CausalRow] = []
        for uid in units:
            ts = int(out_ts.get(uid) or treated_at.get(uid) or start)
            treat = DEFAULT_CAUSAL_BUILDER_POLICY.unit_treated_value if uid in treated_at else DEFAULT_CAUSAL_BUILDER_POLICY.unit_control_value
            y = float(out_sum.get(uid, DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value))
            c = dict(covs.get(uid) or {})
            rows.append(CausalRow(unit_id=uid, timestamp_ms=ts, treatment=treat, outcome=y, covariates=c))

        ds = CausalDataset(rows=rows)
        ds.validate()
        return ds

    def build_diff_in_diff_dataset(
        self,
        event_store: Any,
        *,
        tenant_id: str,
        treated_units: Sequence[str],
        outcome_event: str,
        pre_start_ms: int,
        pre_end_ms: int,
        post_start_ms: int,
        post_end_ms: int,
        outcome_value_path: tuple[str, ...] = ("payload", "amount"),
        max_events: int = DEFAULT_CAUSAL_BUILDER_POLICY.diff_in_diff_max_events,
    ) -> CausalDataset:
        """Build a DiD dataset with rows per unit per period."""

        tid = _require_tenant_id(tenant_id)
        treated = set(str(u) for u in treated_units)

        def _get_path(d: Mapping[str, Any], path: tuple[str, ...]) -> Any:
            cur: Any = d
            for p in path:
                if not isinstance(cur, Mapping):
                    return None
                cur = cur.get(p)
            return cur

        def _agg(start_ms: int, end_ms: int) -> dict[str, float]:
            sums: dict[str, float] = {}
            c = 0
            for ev in _iter_events_compat(event_store, tenant_id=tid, event_type=str(outcome_event), start_ms=int(start_ms), end_ms=int(end_ms)):
                uid = str(ev.get(self.unit_id_key) or "").strip()
                if not uid:
                    continue
                v = _get_path(ev, outcome_value_path)
                try:
                    vf = float(v or DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value)
                except Exception:
                    vf = DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value
                sums[uid] = float(sums.get(uid, DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value)) + float(vf)
                c += 1
                if c >= int(max_events):
                    break
            return sums

        pre = _agg(int(pre_start_ms), int(pre_end_ms))
        post = _agg(int(post_start_ms), int(post_end_ms))

        units = set(pre.keys()) | set(post.keys()) | set(treated)
        rows: list[CausalRow] = []
        for uid in units:
            t = DEFAULT_CAUSAL_BUILDER_POLICY.unit_treated_value if uid in treated else DEFAULT_CAUSAL_BUILDER_POLICY.unit_control_value
            rows.append(CausalRow(unit_id=uid, timestamp_ms=int(pre_end_ms), treatment=t, outcome=float(pre.get(uid, DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value)), covariates={"period": DEFAULT_CAUSAL_BUILDER_POLICY.pre_period_label}))
            rows.append(CausalRow(unit_id=uid, timestamp_ms=int(post_end_ms), treatment=t, outcome=float(post.get(uid, DEFAULT_CAUSAL_BUILDER_POLICY.default_outcome_value)), covariates={"period": DEFAULT_CAUSAL_BUILDER_POLICY.post_period_label}))

        ds = CausalDataset(rows=rows)
        ds.validate()
        return ds
