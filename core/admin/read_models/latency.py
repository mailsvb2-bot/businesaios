from __future__ import annotations

from typing import Any, Dict, List

from config.admin_latency_policy import DEFAULT_ADMIN_LATENCY_POLICY, AdminLatencyPolicy
from core.admin.read_models.common_support import normalize_admin_tenant_id
from core.admin.read_models.latency_support import resolve_window_range


def latency_brief(
    event_store: Any,
    *,
    tenant_id: str = "default",
    days: int = DEFAULT_ADMIN_LATENCY_POLICY.default_days,
    limit: int = DEFAULT_ADMIN_LATENCY_POLICY.default_brief_limit,
    now_ms: int | None = None,
    policy: AdminLatencyPolicy = DEFAULT_ADMIN_LATENCY_POLICY,
) -> dict[str, Any]:
    """Aggregate latency spans into per-button stats (best-effort)."""
    if event_store is None or not hasattr(event_store, "iter_events"):
        return {"top_slowest": [], "window_days": int(days), "samples": 0}

    try:
        days = int(days)
    except Exception:
        days = int(policy.default_days)
    days = max(int(policy.min_days), min(int(policy.max_days), days))
    try:
        limit = int(limit)
    except Exception:
        limit = int(policy.default_brief_limit)
    limit = max(int(policy.min_table_limit), min(int(policy.max_table_limit), limit))

    tenant_scope = normalize_admin_tenant_id(tenant_id)
    start_ms, now_ms = resolve_window_range(days=days, now_ms=now_ms)

    ck_to_btn: dict[str, str] = {}
    per_btn: dict[str, list[int]] = {}
    samples = 0

    for ev in event_store.iter_events(tenant_id=tenant_scope, start_ms=start_ms, end_ms=now_ms, event_type="latency_span"):
        try:
            p = ev.get("payload") or {}
            stage = str(p.get("stage") or "")
            dur = int(p.get("duration_ms") or 0)
            ck = str(p.get("correlation_key") or "") if p.get("correlation_key") is not None else ""
            extra = p.get("extra") or {}
            if stage == "router":
                btn = None
                if isinstance(extra, dict):
                    btn = extra.get("button_key") or extra.get("callback_data") or extra.get("command")
                if btn and ck:
                    ck_to_btn[ck] = str(btn)
                continue
            if stage != "execute":
                continue
            samples += 1
            btn_key = ck_to_btn.get(ck) if ck else None
            if not btn_key:
                btn_key = "unknown"
            per_btn.setdefault(str(btn_key), []).append(max(0, dur))
        except Exception:
            continue

    def _pct(xs: list[int], q: float) -> int:
        if not xs:
            return 0
        ys = sorted(xs)
        i = int(round((len(ys) - 1) * float(q)))
        i = max(0, min(len(ys) - 1, i))
        return int(ys[i])

    rows: list[dict[str, Any]] = []
    for btn, durs in per_btn.items():
        if not durs:
            continue
        rows.append(
            {
                "button": str(btn)[: int(policy.button_key_max_len)],
                "count": int(len(durs)),
                "p50_ms": _pct(durs, float(policy.p50_quantile)),
                "p95_ms": _pct(durs, float(policy.p95_quantile)),
                "max_ms": _pct(durs, float(policy.p100_quantile)),
                "mean_ms": int(sum(durs) / max(1, len(durs))),
            }
        )
    rows.sort(key=lambda r: (int(r.get("p95_ms") or 0), int(r.get("count") or 0)), reverse=True)
    return {"top_slowest": rows[:limit], "window_days": int(days), "samples": int(samples)}


def latency_breakdown(
    event_store: Any,
    *,
    tenant_id: str = "default",
    days: int = DEFAULT_ADMIN_LATENCY_POLICY.default_days,
    limit: int = DEFAULT_ADMIN_LATENCY_POLICY.default_breakdown_limit,
    now_ms: int | None = None,
    policy: AdminLatencyPolicy = DEFAULT_ADMIN_LATENCY_POLICY,
) -> dict[str, Any]:
    """Per-button latency stats with stage split: router/decide/execute/telegram_api."""
    if event_store is None or not hasattr(event_store, "iter_events"):
        return {"rows": [], "window_days": int(days), "samples": 0}

    try:
        days = int(days)
    except Exception:
        days = int(policy.default_days)
    days = max(int(policy.min_days), min(int(policy.max_days), days))
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

            if stage in {"router", "decide", "execute"}:
                if not (isinstance(extra, dict) and ("update_id" in extra or extra.get("kind") == "telegram_update")):
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

    def _pct(xs: list[int], q: float) -> int:
        if not xs:
            return 0
        ys = sorted(xs)
        i = int(round((len(ys) - 1) * float(q)))
        i = max(0, min(len(ys) - 1, i))
        return int(ys[i])

    rows: list[dict[str, Any]] = []
    for btn, by_stage in per_btn_stage.items():
        row: dict[str, Any] = {"button": str(btn)[: int(policy.button_key_max_len)]}
        score = 0
        for stage in ["decide", "execute", "telegram_api"]:
            durs = by_stage.get(stage) or []
            if not durs:
                continue
            row[f"{stage}_count"] = int(len(durs))
            row[f"{stage}_p50_ms"] = _pct(durs, float(policy.p50_quantile))
            row[f"{stage}_p95_ms"] = _pct(durs, float(policy.p95_quantile))
            row[f"{stage}_max_ms"] = _pct(durs, float(policy.p100_quantile))
            score = max(score, int(row.get(f"{stage}_p95_ms") or 0))
        row["score_p95_ms"] = int(score)
        rows.append(row)

    rows.sort(key=lambda r: int(r.get("score_p95_ms") or 0), reverse=True)
    return {"rows": rows[:limit], "window_days": int(days), "samples": int(samples)}


def sla_breaches_brief(
    event_store: Any,
    *,
    tenant_id: str = "default",
    days: int = DEFAULT_ADMIN_LATENCY_POLICY.default_days,
    limit: int = DEFAULT_ADMIN_LATENCY_POLICY.default_breaches_limit,
    now_ms: int | None = None,
    policy: AdminLatencyPolicy = DEFAULT_ADMIN_LATENCY_POLICY,
) -> dict[str, Any]:
    """Recent latency SLA breaches emitted by perf.watchdog."""
    if event_store is None or not hasattr(event_store, "iter_events"):
        return {"breaches": [], "window_days": int(days)}
    try:
        days = int(days)
    except Exception:
        days = int(policy.default_days)
    days = max(int(policy.min_days), min(int(policy.max_days), days))
    try:
        limit = int(limit)
    except Exception:
        limit = int(policy.default_breaches_limit)
    limit = max(int(policy.min_limit), min(int(policy.max_breaches_limit), limit))

    tenant_scope = normalize_admin_tenant_id(tenant_id)
    start_ms, now_ms = resolve_window_range(days=days, now_ms=now_ms)
    breaches: list[dict[str, Any]] = []

    for ev in event_store.iter_events(tenant_id=tenant_scope, start_ms=start_ms, end_ms=now_ms, event_type="latency_sla_breached"):
        try:
            p = ev.get("payload") or {}
            breaches.append(
                {
                    "ts_ms": int(p.get("ts_ms") or 0),
                    "budget_ms": int(p.get("budget_ms") or 0),
                    "offenders": p.get("offenders") or [],
                }
            )
        except Exception:
            continue
    breaches.sort(key=lambda r: int(r.get("ts_ms") or 0), reverse=True)
    return {"breaches": breaches[:limit], "window_days": int(days)}
