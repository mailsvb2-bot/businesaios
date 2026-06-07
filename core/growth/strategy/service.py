from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from config.strategic_growth_policy import DEFAULT_GROWTH_STRATEGY_SERVICE_POLICY, GrowthStrategyServicePolicy

from .backlog_store import (
    append_experiment,
    append_hypothesis,
    append_score,
    append_strategy_snapshot,
    list_backlog,
    now_ms,
    set_hypothesis_state,
)
from .contracts import ExperimentSpecV1, GrowthGoalV1, GrowthHypothesisV1, GrowthSignalV1, StrategyPlanV1
from .llm_generator import generate_hypotheses
from .scoring import rank_hypotheses, score_hypothesis
from .signals import build_signals


class GrowthStrategyService:
    def __init__(
        self,
        *,
        event_store: Any,
        llm: Any | None = None,
        policy: GrowthStrategyServicePolicy | None = None,
    ) -> None:
        self._event_store = event_store
        self._llm = llm
        self._policy = policy or DEFAULT_GROWTH_STRATEGY_SERVICE_POLICY

    def generate_backlog(
        self,
        *,
        tenant_id: str,
        user_id: str,
        decision_id: str,
        correlation_id: str,
        goal: GrowthGoalV1 | None = None,
        n: int | None = None,
        model: str = "",
    ) -> StrategyPlanV1:
        g = goal or GrowthGoalV1()
        signals = build_signals(self._event_store, tenant_id=str(tenant_id))
        hypothesis_count = self._policy.default_hypothesis_count if n is None else int(n)
        append_strategy_snapshot(self._event_store, tenant_id=str(tenant_id), user_id=str(user_id), decision_id=str(decision_id), correlation_id=str(correlation_id), signals=signals)

        hyps: tuple[GrowthHypothesisV1, ...] = ()
        if self._llm is not None:
            hyps = generate_hypotheses(self._llm, tenant_id=str(tenant_id), goal=g, signals=signals, n=hypothesis_count, model=str(model or ""))
        if not hyps:
            hyps = _fallback_hypotheses(tenant_id=str(tenant_id), signals=signals, goal=g)

        for h in hyps:
            append_hypothesis(self._event_store, tenant_id=str(tenant_id), user_id=str(user_id), decision_id=str(decision_id), correlation_id=str(correlation_id), h=h)
            append_score(self._event_store, tenant_id=str(tenant_id), user_id=str(user_id), decision_id=str(decision_id), correlation_id=str(correlation_id), score=score_hypothesis(h))

        scored = rank_hypotheses(hyps)
        score_by_id = {item.hypothesis_id: item.score for item in scored}
        ranked = sorted(hyps, key=lambda h: score_by_id.get(h.hypothesis_id, self._policy.zero_rank_score), reverse=True)
        return StrategyPlanV1(tenant_id=str(tenant_id), created_ms=now_ms(), goal=g, signals=signals, top_hypotheses=tuple(ranked), notes=("llm" if self._llm is not None else "no_llm", "advisory_ranking_only",))

    def backlog(self, *, tenant_id: str, limit: int | None = None):
        backlog_limit = self._policy.default_backlog_limit if limit is None else int(limit)
        return list_backlog(self._event_store, tenant_id=str(tenant_id), limit=backlog_limit)

    def accept_hypothesis(self, *, tenant_id: str, user_id: str, decision_id: str, correlation_id: str, hypothesis_id: str, note: str = "") -> str:
        return set_hypothesis_state(self._event_store, tenant_id=str(tenant_id), user_id=str(user_id), decision_id=str(decision_id), correlation_id=str(correlation_id), hypothesis_id=str(hypothesis_id), state="accepted", note=str(note or ""))

    def reject_hypothesis(self, *, tenant_id: str, user_id: str, decision_id: str, correlation_id: str, hypothesis_id: str, note: str = "") -> str:
        return set_hypothesis_state(self._event_store, tenant_id=str(tenant_id), user_id=str(user_id), decision_id=str(decision_id), correlation_id=str(correlation_id), hypothesis_id=str(hypothesis_id), state="rejected", note=str(note or ""))

    def create_experiment_from_hypothesis(self, *, tenant_id: str, user_id: str, decision_id: str, correlation_id: str, h: GrowthHypothesisV1) -> ExperimentSpecV1:
        exp = ExperimentSpecV1(
            experiment_id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            created_ms=now_ms(),
            hypothesis_id=str(h.hypothesis_id),
            name=str(h.title)[: self._policy.max_experiment_name_length],
            stage=h.stage,
            channel=h.channel,
            primary_metric=str(h.metric or "profit_minor"),
            duration_days=int(h.horizon_days or self._policy.default_duration_days),
            steps=_default_steps(h, policy=self._policy),
            payload=dict(h.action_hints or {}),
        )
        append_experiment(self._event_store, tenant_id=str(tenant_id), user_id=str(user_id), decision_id=str(decision_id), correlation_id=str(correlation_id), exp=exp)
        return exp


def _default_steps(
    h: GrowthHypothesisV1,
    *,
    policy: GrowthStrategyServicePolicy = DEFAULT_GROWTH_STRATEGY_SERVICE_POLICY,
) -> tuple[str, ...]:
    steps = list(policy.base_steps)
    if h.channel in policy.paid_channels:
        steps.insert(1, policy.paid_channel_creative_step)
    if h.stage == "retention":
        steps.insert(1, policy.retention_segment_step)
    return tuple(steps)


def _fallback_hypotheses(*, tenant_id: str, signals: GrowthSignalV1, goal: GrowthGoalV1) -> tuple[GrowthHypothesisV1, ...]:
    now = int(time.time() * 1000)
    out: list[GrowthHypothesisV1] = []
    out.append(
        GrowthHypothesisV1(
            hypothesis_id=str(uuid.uuid4()),
            created_ms=now,
            tenant_id=str(tenant_id),
            stage="activation",
            channel="telegram",
            title="Сократить путь до оплаты: 1 кнопка + готовый оффер",
            mechanism="Уменьшаем когнитивную нагрузку: после лида сразу даём 1 понятное предложение и кнопку оплаты.",
            expected_impact="+10% conversion lead→purchase за 14 дней",
            effort="medium",
            risk="low",
            metric="conversion_lead_to_purchase_pct",
            horizon_days=int(goal.horizon_days or 14),
            action_hints={"type": "telegram_flow", "flow": "offer_to_pay"},
        )
    )
    out.append(
        GrowthHypothesisV1(
            hypothesis_id=str(uuid.uuid4()),
            created_ms=now,
            tenant_id=str(tenant_id),
            stage="retention",
            channel="telegram",
            title="Авто-followup через 24ч/72ч: полезность + кейс",
            mechanism="Тёплые лиды забывают. Триггеры возвращают внимание и доводят до покупки.",
            expected_impact="+5-10% revenue в 14 дней",
            effort="low",
            risk="low",
            metric="revenue_minor",
            horizon_days=int(goal.horizon_days or 14),
            action_hints={"type": "telegram_followup", "schedule": [24, 72]},
        )
    )
    if "ads_apply_used" in set(signals.notes):
        out.append(
            GrowthHypothesisV1(
                hypothesis_id=str(uuid.uuid4()),
                created_ms=now,
                tenant_id=str(tenant_id),
                stage="acquisition",
                channel="meta_ads",
                title="Обновить креативы (3 варианта) по боли/выгоде",
                mechanism="Свежие креативы снижают CPM/CPC и дают больше лидов при том же бюджете.",
                expected_impact="+10% leads при том же spend за 14 дней",
                effort="medium",
                risk="medium",
                metric="leads",
                horizon_days=int(goal.horizon_days or 14),
                action_hints={"type": "ads_creative_refresh", "variants": 3},
            )
        )
    out.append(
        GrowthHypothesisV1(
            hypothesis_id=str(uuid.uuid4()),
            created_ms=now,
            tenant_id=str(tenant_id),
            stage="revenue",
            channel="telegram",
            title="Пакетирование: базовый + премиум (upsell)",
            mechanism="Часть клиентов готова платить больше за быстрый результат/доп. поддержку.",
            expected_impact="+10% profit в 21 день",
            effort="high",
            risk="medium",
            metric="profit_minor",
            horizon_days=max(14, int(goal.horizon_days or 14)),
            action_hints={"type": "pricing_package", "tiers": ["basic", "premium"]},
        )
    )
    return tuple(out)
