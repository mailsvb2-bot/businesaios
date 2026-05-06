from __future__ import annotations

CANON_THIN_HANDLER = True


import logging
from typing import Any, Dict, List

from runtime.ports.effects import EffectsPort
from runtime.tenancy import as_tenant_id

from runtime.ads import bind_runtime_state, maturity_gate, policy_store
from runtime.governance import ProfitMetricsService
from runtime.ads import DatasetBuilder, OPEGate, RLTrainer, RewardComputer, RewardWindow

logger = logging.getLogger(__name__)

ACTION_NAME = "ads_rl_train_tick@v1"


def handle_ads_rl_train_tick(payload: Dict[str, Any], effects: EffectsPort, env: Any, *, event_store: Any) -> Any:
    p = payload or {}
    bind_runtime_state(event_store=event_store)
    tenant_id = as_tenant_id(str(p.get("tenant_id") or ""))
    lookback_days = int(p.get("lookback_days") or 14)
    decision_ids: List[str] = [str(x) for x in (p.get("decision_ids") or []) if str(x).strip()]

    if not decision_ids:
        return effects.send_message(
            decision_id=str(p.get("decision_id") or ""),
            correlation_id=str(p.get("correlation_id") or ""),
            user_id=str(p.get("user_id") or ""),
            chat_id=str(p.get("chat_id") or ""),
            text="🧠 RL Train: нет decision_ids для обучения (передай список выполненных решений).",
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={"reason": "no_decision_ids"},
        )

    matured = [d for d in decision_ids if maturity_gate.is_mature(tenant_id=str(tenant_id), decision_id=str(d))]
    if len(matured) < max(5, int(p.get("min_matured") or 5)):
        return effects.send_message(
            decision_id=str(p.get("decision_id") or ""),
            correlation_id=str(p.get("correlation_id") or ""),
            user_id=str(p.get("user_id") or ""),
            chat_id=str(p.get("chat_id") or ""),
            text=f"⏳ RL Train: недостаточно matured решений ({len(matured)}/{len(decision_ids)}).",
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={"reason": "too_few_matured", "matured": len(matured), "total": len(decision_ids)},
        )

    pm = ProfitMetricsService(event_store=event_store)
    reward = RewardComputer(profit_metrics=pm, window=RewardWindow(pre_days=3, post_days=3))
    builder = DatasetBuilder(reward_computer=reward)
    transitions = builder.build_for_decisions(
        tenant_id=str(tenant_id),
        decision_ids=matured,
        lookback_days=lookback_days,
    )

    trainer = RLTrainer(store=policy_store, ope_gate=OPEGate(min_transitions=int(p.get("min_transitions") or 30)))
    report = trainer.train(tenant_id=str(tenant_id), transitions=transitions)

    try:
        effects.track_event(
            decision_id=str(p.get("decision_id") or ""),
            correlation_id=str(p.get("correlation_id") or ""),
            user_id=str(p.get("user_id") or ""),
            event_type="ads_rl_train_report@v1",
            payload={
                "tenant_id": str(tenant_id),
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
        logger.warning("telemetry emission failed", extra={"component": __name__, "error": str(exc)})

    if not report.ok:
        return effects.send_message(
            decision_id=str(p.get("decision_id") or ""),
            correlation_id=str(p.get("correlation_id") or ""),
            user_id=str(p.get("user_id") or ""),
            chat_id=str(p.get("chat_id") or ""),
            text=f"🧠 RL Train: пропуск ({report.reason}/{report.ope_reason}) n={report.n}",
            track_event_type="ads_rl_train_skipped@v1",
            track_payload={"reason": report.reason, "ope": report.ope_reason, "n": report.n},
        )

    return effects.send_message(
        decision_id=str(p.get("decision_id") or ""),
        correlation_id=str(p.get("correlation_id") or ""),
        user_id=str(p.get("user_id") or ""),
        chat_id=str(p.get("chat_id") or ""),
        text=f"✅ RL Train: policy_version={report.policy_version}, n={report.n}, avg_reward_minor={report.avg_reward_minor}",
        track_event_type="ads_rl_train_ok@v1",
        track_payload={"policy_version": report.policy_version, "n": report.n, "avg_reward_minor": report.avg_reward_minor},
    )
