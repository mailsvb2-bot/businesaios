from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from admin.admin_tenant_scope import normalize_admin_tenant_id
from config.admin_latency_read_model_policy import DEFAULT_ADMIN_LATENCY_READ_MODEL_POLICY, AdminLatencyReadModelPolicy
from core.observability.latency_window import resolve_window_range


@dataclass(frozen=True)
class LatencyButtonRow:
    button_key: str
    samples: int
    p50_ms: int
    p95_ms: int
    max_ms: int


@dataclass(frozen=True)
class LatencyDashboardModel:
    tenant_id: str
    days: int
    samples: int
    rows: tuple[LatencyButtonRow, ...]


def _percentile(values: Iterable[int], pct: float) -> int:
    data = sorted(int(v) for v in values)
    if not data:
        return 0
    idx = int(round((len(data) - 1) * float(pct)))
    idx = max(0, min(len(data) - 1, idx))
    return max(0, int(data[idx]))


def read_latency_dashboard(
    *,
    event_store: Any,
    tenant_id: str,
    days: int,
    limit: int = 20,
    now_ms: int | None = None,
    policy: AdminLatencyReadModelPolicy = DEFAULT_ADMIN_LATENCY_READ_MODEL_POLICY,
) -> LatencyDashboardModel:
    if event_store is None or not hasattr(event_store, "iter_events"):
        return LatencyDashboardModel(tenant_id=normalize_admin_tenant_id(tenant_id), days=int(days), samples=0, rows=())

    try:
        limit = int(limit)
    except Exception:
        limit = int(policy.default_brief_limit)
    limit = max(int(policy.min_table_limit), min(int(policy.max_table_limit), limit))

    tenant_scope = normalize_admin_tenant_id(tenant_id)
    start_ms, now_ms = resolve_window_range(days=days, now_ms=now_ms)

    ck_to_btn: dict[str, str] = {}
    per_btn_stage: dict[str, dict[str, list[int]]] = {}
    samples = 0
    wanted = {"router", "decide", "execute", "telegram_api"}

    for ev in event_store.iter_events(tenant_id=tenant_scope, start_ms=start_ms, end_ms=now_ms, event_type="latency_span"):
        try:
            p = ev.get("payload") or {}
            stage = str(p.get("stage") or "")
            if stage not in wanted:
                continue
            dur = int(p.get("duration_ms") or 0)
            ck = str(p.get("correlation_key") or "") if p.get("correlation_key") is not None else ""
            extra = p.get("extra") or {}

            if stage in {"router", "decide", "execute"} and not (isinstance(extra, dict) and ("update_id" in extra or extra.get("kind") == "telegram_update")):
                continue

            if stage == "router":
                btn = None
                if isinstance(extra, dict):
                    btn = extra.get("button_key") or extra.get("callback_data") or extra.get("command") or extra.get("text")
                if btn and ck:
                    ck_to_btn[ck] = str(btn)
                continue

            samples += 1
            btn_key = ck_to_btn.get(ck) if ck else None
            if not btn_key:
                btn_key = "unknown"
            per_btn_stage.setdefault(str(btn_key), {}).setdefault(stage, []).append(max(0, dur))
        except Exception:
            continue

    rows: list[LatencyButtonRow] = []
    for button_key, stage_map in per_btn_stage.items():
        merged: list[int] = []
        for vals in stage_map.values():
            merged.extend(vals)
        rows.append(
            LatencyButtonRow(
                button_key=button_key,
                samples=len(merged),
                p50_ms=_percentile(merged, 0.50),
                p95_ms=_percentile(merged, 0.95),
                max_ms=max(merged) if merged else 0,
            )
        )
    rows.sort(key=lambda r: (r.p95_ms, r.max_ms, r.samples), reverse=True)
    return LatencyDashboardModel(tenant_id=tenant_scope, days=int(days), samples=int(samples), rows=tuple(rows[:limit]))

def latency_breakdown(
    event_store: Any,
    *,
    tenant_id: str = "default",
    days: int = 7,
    limit: int = 20,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Return the canonical per-button latency dashboard as a serializable dict."""

    model = read_latency_dashboard(
        event_store=event_store,
        tenant_id=tenant_id,
        days=days,
        limit=limit,
        now_ms=now_ms,
    )
    return {
        "tenant_id": model.tenant_id,
        "days": int(model.days),
        "samples": int(model.samples),
        "rows": [
            {
                "button_key": row.button_key,
                "samples": int(row.samples),
                "p50_ms": int(row.p50_ms),
                "p95_ms": int(row.p95_ms),
                "max_ms": int(row.max_ms),
            }
            for row in model.rows
        ],
    }


def latency_brief(
    event_store: Any,
    *,
    tenant_id: str = "default",
    days: int = 7,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Return compact latency health for admin overview surfaces."""

    model = read_latency_dashboard(
        event_store=event_store,
        tenant_id=tenant_id,
        days=days,
        limit=1,
        now_ms=now_ms,
    )
    worst = model.rows[0] if model.rows else None
    return {
        "tenant_id": model.tenant_id,
        "days": int(model.days),
        "samples": int(model.samples),
        "worst_button_key": worst.button_key if worst is not None else "",
        "worst_p95_ms": int(worst.p95_ms) if worst is not None else 0,
        "worst_max_ms": int(worst.max_ms) if worst is not None else 0,
    }


def sla_breaches_brief(
    event_store: Any,
    *,
    tenant_id: str = "default",
    days: int = 7,
    p95_threshold_ms: int = 1500,
    now_ms: int | None = None,
) -> dict[str, Any]:
    """Return count of button latency rows whose p95 exceeds the SLA threshold."""

    threshold = max(0, int(p95_threshold_ms))
    model = read_latency_dashboard(
        event_store=event_store,
        tenant_id=tenant_id,
        days=days,
        limit=100,
        now_ms=now_ms,
    )
    breaches = [row for row in model.rows if int(row.p95_ms) > threshold]
    return {
        "tenant_id": model.tenant_id,
        "days": int(model.days),
        "threshold_ms": threshold,
        "breaches": len(breaches),
        "buttons": [row.button_key for row in breaches],
    }


__all__ = [
    "LatencyButtonRow",
    "LatencyDashboardModel",
    "latency_breakdown",
    "latency_brief",
    "read_latency_dashboard",
    "sla_breaches_brief",
]

