from __future__ import annotations

import logging
from typing import Any

from runtime.ads import (
    DatasetBuilder,
    OPEGate,
    RewardComputer,
    RewardWindow,
    RLTrainer,
    bind_runtime_state,
    maturity_gate,
    policy_store,
)
from runtime.governance import ProfitMetricsService
from runtime.ports.effects import EffectsPort
from runtime.tenancy import as_tenant_id

CANON_THIN_HANDLER = True

logger = logging.getLogger(__name__)

ACTION_NAME = "ads_rl_train_tick@v1"


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise RuntimeError(f"{field.upper()}_REQUIRED")
    return value


def _send(
    *,
    effects: EffectsPort,
    tenant_id: str,
    user_id: str,
    decision_id: str,
    correlation_id: str,
    text: str,
    track_event_type: str,
    track_payload: dict[str, Any],
):
    payload = dict(track_payload)
    payload.setdefault("tenant_id", tenant_id)
    return effects.send_message(
        decision_id=decision_id,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
        text=text,
        track_event_type=track_event_type,
        track_payload=payload,
    )


def handle_ads_rl_train_tick(
    payload: dict[str, Any],
    effects: EffectsPort,
    env: Any,
    *,
    event_store: Any,
) -> Any:
    body = dict(payload or {})
    bind_runtime_state(event_store=event_store)
    tenant_id = str(as_tenant_id(_required_text(body, "tenant_id")))
    user_id = _required_text(body, "user_id")
    decision_id = str(env.decision.decision_id)
    correlation_id = str(env.decision.correlation_id)
    lookback_days = int(body.get("lookback_days") or 14)
    decision_ids = [
        str(item)
        for item in (body.get("decision_ids") or [])
        if str(item).strip()
    ]

    if not decision_ids:
        return _send(
            effects=effects,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            text="🧠 RL Train: нет decision_ids для обучения (передай список выполненных решений).",
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={"reason": "no_decision_ids"},
        )

    matured = [
        item
        for item in decision_ids
        if maturity_gate.is_mature(
            tenant_id=tenant_id,
            decision_id=item,
        )
    ]
    minimum_matured = max(5, int(body.get("min_matured") or 5))
    if len(matured) < minimum_matured:
        return _send(
            effects=effects,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            text=(
                "⏳ RL Train: недостаточно matured решений "
                f"({len(matured)}/{len(decision_ids)})."
            ),
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={
                "reason": "too_few_matured",
                "matured": len(matured),
                "total": len(decision_ids),
            },
        )

    metrics = ProfitMetricsService(event_store=event_store)
    reward = RewardComputer(
        profit_metrics=metrics,
        window=RewardWindow(pre_days=3, post_days=3),
    )
    builder = DatasetBuilder(reward_computer=reward)
    transitions = builder.build_for_decisions(
        tenant_id=tenant_id,
        decision_ids=matured,
        lookback_days=lookback_days,
    )

    trainer = RLTrainer(
        store=policy_store,
        ope_gate=OPEGate(
            min_transitions=int(body.get("min_transitions") or 30)
        ),
    )
    report = trainer.train(
        tenant_id=tenant_id,
        transitions=transitions,
    )

    try:
        effects.track_event(
            decision_id=decision_id,
            correlation_id=correlation_id,
            user_id=user_id,
            event_type="ads_rl_train_report@v1",
            payload={
                "tenant_id": tenant_id,
                "ok": bool(report.ok),
                "reason": str(report.reason),
                "n": int(report.n),
                "policy_version": report.policy_version,
                "ope_reason": report.ope_reason,
                "avg_reward_minor": report.avg_reward_minor,
            },
            source="ads_rl",
        )
    except Exception as exc:
        logger.warning(
            "telemetry emission failed",
            extra={"component": __name__, "error": str(exc)},
        )

    if not report.ok:
        return _send(
            effects=effects,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            text=(
                f"🧠 RL Train: пропуск ({report.reason}/{report.ope_reason}) "
                f"n={report.n}"
            ),
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={
                "reason": report.reason,
                "ope": report.ope_reason,
                "n": report.n,
            },
        )

    return _send(
        effects=effects,
        tenant_id=tenant_id,
        user_id=user_id,
        decision_id=decision_id,
        correlation_id=correlation_id,
        text=(
            "✅ RL Train: "
            f"policy_version={report.policy_version}, "
            f"n={report.n}, avg_reward_minor={report.avg_reward_minor}"
        ),
        track_event_type="ads_rl_train_ok@v1",
        track_payload={
            "policy_version": report.policy_version,
            "n": report.n,
            "avg_reward_minor": report.avg_reward_minor,
        },
    )
