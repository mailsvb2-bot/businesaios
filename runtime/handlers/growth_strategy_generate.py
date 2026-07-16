from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from execution.verification.evidence_types import evidence_status_is_positive
from runtime.growth import GrowthGoalV1, GrowthStrategyService
from runtime.ports.effects import EffectsPort

CANON_THIN_HANDLER = True
ACTION_NAME = "growth_strategy_generate@v1"


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise RuntimeError(f"{key.upper()}_REQUIRED")
    return value


def _delivery_evidence(delivery: object) -> dict[str, Any] | None:
    if not isinstance(delivery, Mapping):
        return None
    for key in ("router_evidence", "evidence", "verification"):
        value = delivery.get(key)
        if isinstance(value, Mapping) and str(value.get("source") or "").strip():
            return dict(value)
    return None


def _proof_is_positive(proof: Mapping[str, Any] | None) -> bool:
    if not isinstance(proof, Mapping) or proof.get("verified") is False:
        return False
    return evidence_status_is_positive(proof.get("status")) or proof.get("verified") is True


def _generation_evidence(*, event_id: str, tenant_id: str, plan) -> dict[str, Any]:
    return {
        "source": "ledger",
        "verified": True,
        "status": "verified",
        "code": "growth_strategy_generation_recorded",
        "external_refs": [str(event_id)],
        "confidence": 1.0,
        "payload": {
            "tenant_id": str(tenant_id),
            "hypothesis_ids": [
                str(hypothesis.hypothesis_id)
                for hypothesis in plan.top_hypotheses
            ],
        },
    }


def handle_growth_strategy_generate(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
    llm: Any = None,
    track_event_type: str = ACTION_NAME,
) -> Any:
    body = dict(payload or {})
    tenant_id = _required_text(body, "tenant_id")
    user_id = _required_text(body, "user_id")
    decision_id = str(env.decision.decision_id)
    correlation_id = str(env.decision.correlation_id)
    event_type = str(track_event_type or ACTION_NAME).strip() or ACTION_NAME

    goal = _parse_goal(body.get("goal") or {})
    n = int(body.get("n") or 8)
    model = str(body.get("model") or "")

    service = GrowthStrategyService(event_store=event_store, llm=llm)
    plan, completion_event_id = service.generate_backlog_with_proof(
        tenant_id=tenant_id,
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        goal=goal,
        n=n,
        model=model,
    )
    generation_evidence = _generation_evidence(
        event_id=completion_event_id,
        tenant_id=tenant_id,
        plan=plan,
    )

    notification = effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=_render_plan(plan),
        reply_markup=_menu_markup(),
        callback_query_id=body.get("callback_query_id"),
        critical=False,
        channel=str(body.get("channel") or "telegram"),
        channel_policy=(
            dict(body.get("channel_policy") or {})
            if isinstance(body.get("channel_policy"), Mapping)
            else None
        ),
        track_event_type=event_type,
        track_payload={
            "tenant_id": tenant_id,
            "completion_event_id": completion_event_id,
            "hypothesis_count": len(plan.top_hypotheses),
            "canonical_action": ACTION_NAME,
        },
    )
    notification_evidence = _delivery_evidence(notification)
    notification_ok = bool(notification.get("ok")) if isinstance(notification, Mapping) else bool(notification)
    composite_ok = bool(
        completion_event_id
        and notification_ok
        and _proof_is_positive(notification_evidence)
    )

    return {
        "ok": composite_ok,
        "status": "verified" if composite_ok else "failed",
        "plan": plan,
        "completion_event_id": completion_event_id,
        "notification": notification,
        "router_evidence": generation_evidence if composite_ok else None,
        "feedback": {
            "connector_snapshots": [generation_evidence, notification_evidence]
            if composite_ok and notification_evidence is not None
            else []
        },
    }


def _parse_goal(data: dict[str, Any]) -> GrowthGoalV1:
    try:
        if not isinstance(data, dict):
            return GrowthGoalV1()
        base = GrowthGoalV1()
        return GrowthGoalV1(
            primary_stage=str(data.get("primary_stage") or base.primary_stage),  # type: ignore[arg-type]
            horizon_days=int(data.get("horizon_days") or base.horizon_days),
            kpi=str(data.get("kpi") or base.kpi),
            target_delta_pct=float(data.get("target_delta_pct") or base.target_delta_pct),
            constraints=tuple(data.get("constraints") or base.constraints),
        )
    except Exception:
        return GrowthGoalV1()


def _render_plan(plan) -> str:
    signals = plan.signals
    lines = [
        "🧠 AI Growth Strategy — backlog гипотез",
        "",
        f"Сегодня: лиды={signals.leads_today}, spend={signals.spend_today_minor}, revenue={signals.revenue_today_minor}, profit={signals.profit_today_minor}",
        f"Retention: D1={signals.retention_d1_pct:.1f}%, D7={signals.retention_d7_pct:.1f}% | Конверсия lead→purchase={signals.conversion_lead_to_purchase_pct:.1f}%",
    ]
    if signals.top_channels:
        lines.append("Топ-каналы: " + ", ".join(signals.top_channels))
    lines.append("")
    for index, hypothesis in enumerate(plan.top_hypotheses[:8], 1):
        lines.append(f"{index}) [{hypothesis.stage}/{hypothesis.channel}] {hypothesis.title}")
        if hypothesis.expected_impact:
            lines.append(f"   эффект: {hypothesis.expected_impact}")
        if hypothesis.mechanism:
            lines.append(f"   почему: {hypothesis.mechanism}")
        lines.append(
            f"   effort={hypothesis.effort}, risk={hypothesis.risk}, metric={hypothesis.metric}, horizon={hypothesis.horizon_days}d"
        )
        lines.append(f"   id={hypothesis.hypothesis_id}")
        lines.append("")
    lines.append("Дальше: открой backlog и прими/отклони гипотезы.")
    return "\n".join(lines).strip()


def _menu_markup() -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [{"text": "📋 Backlog", "callback_data": "growth:backlog"}],
            [{"text": "🔁 Сгенерировать ещё", "callback_data": "growth:generate"}],
        ]
    }
