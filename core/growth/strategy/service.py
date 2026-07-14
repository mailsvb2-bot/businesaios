from __future__ import annotations

import time
import uuid
from dataclasses import replace
from typing import Any

from config.strategic_growth_policy import DEFAULT_GROWTH_STRATEGY_SERVICE_POLICY, GrowthStrategyServicePolicy

from .backlog_store import (
    append_experiment,
    append_hypothesis,
    append_score,
    append_strategy_generated,
    append_strategy_snapshot,
    list_backlog,
    load_generated_plan_for_decision,
    now_ms,
    set_hypothesis_state,
)
from .contracts import ExperimentSpecV1, GrowthGoalV1, GrowthHypothesisV1, GrowthSignalV1, StrategyPlanV1
from .llm_generator import generate_hypotheses
from .plan_manifest import load_plan_manifest, persist_plan_manifest
from .scoring import rank_hypotheses, score_hypothesis
from .signals import build_signals

_GROWTH_ID_NAMESPACE = uuid.UUID("470d7825-fc2f-4ce9-bf89-f40954ecf226")


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
        plan, _proof_event_id = self.generate_backlog_with_proof(
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            goal=goal,
            n=n,
            model=model,
        )
        return plan

    def generate_backlog_with_proof(
        self,
        *,
        tenant_id: str,
        user_id: str,
        decision_id: str,
        correlation_id: str,
        goal: GrowthGoalV1 | None = None,
        n: int | None = None,
        model: str = "",
    ) -> tuple[StrategyPlanV1, str]:
        tenant = str(tenant_id).strip()
        user = str(user_id).strip()
        decision = str(decision_id).strip()
        correlation = str(correlation_id).strip()
        if not tenant:
            raise RuntimeError("TENANT_ID_REQUIRED")
        if not user:
            raise RuntimeError("USER_ID_REQUIRED")
        if not decision:
            raise RuntimeError("DECISION_ID_REQUIRED")
        if not correlation:
            raise RuntimeError("CORRELATION_ID_REQUIRED")

        completed = load_generated_plan_for_decision(
            self._event_store,
            tenant_id=tenant,
            decision_id=decision,
        )
        if completed is not None:
            return completed

        manifest = load_plan_manifest(
            self._event_store,
            tenant_id=tenant,
            decision_id=decision,
        )
        if manifest is not None:
            plan = manifest[0]
        else:
            plan = self._build_plan(
                tenant_id=tenant,
                decision_id=decision,
                goal=goal or GrowthGoalV1(),
                n=n,
                model=model,
            )
            persist_plan_manifest(
                self._event_store,
                tenant_id=tenant,
                user_id=user,
                decision_id=decision,
                correlation_id=correlation,
                plan=plan,
            )

        self._persist_plan_details(
            plan=plan,
            tenant_id=tenant,
            user_id=user,
            decision_id=decision,
            correlation_id=correlation,
        )
        completion_event_id = append_strategy_generated(
            self._event_store,
            tenant_id=tenant,
            user_id=user,
            decision_id=decision,
            correlation_id=correlation,
            goal=plan.goal,
            hypothesis_ids=tuple(
                hypothesis.hypothesis_id
                for hypothesis in plan.top_hypotheses
            ),
            created_ms=int(plan.created_ms),
            notes=tuple(plan.notes),
        )
        durable = load_generated_plan_for_decision(
            self._event_store,
            tenant_id=tenant,
            decision_id=decision,
        )
        if durable is not None:
            return durable
        return plan, completion_event_id

    def _build_plan(
        self,
        *,
        tenant_id: str,
        decision_id: str,
        goal: GrowthGoalV1,
        n: int | None,
        model: str,
    ) -> StrategyPlanV1:
        signals = build_signals(self._event_store, tenant_id=tenant_id)
        hypothesis_count = (
            self._policy.default_hypothesis_count
            if n is None
            else int(n)
        )
        hypotheses: tuple[GrowthHypothesisV1, ...] = ()
        if self._llm is not None:
            hypotheses = tuple(
                generate_hypotheses(
                    self._llm,
                    tenant_id=tenant_id,
                    goal=goal,
                    signals=signals,
                    n=hypothesis_count,
                    model=str(model or ""),
                )
            )
        if not hypotheses:
            hypotheses = _fallback_hypotheses(
                tenant_id=tenant_id,
                decision_id=decision_id,
                signals=signals,
                goal=goal,
            )
        hypotheses = _stabilize_hypotheses(
            hypotheses,
            tenant_id=tenant_id,
            decision_id=decision_id,
        )
        scored = rank_hypotheses(hypotheses)
        score_by_id = {
            item.hypothesis_id: item.score
            for item in scored
        }
        ranked = tuple(
            sorted(
                hypotheses,
                key=lambda hypothesis: score_by_id.get(
                    hypothesis.hypothesis_id,
                    self._policy.zero_rank_score,
                ),
                reverse=True,
            )
        )
        return StrategyPlanV1(
            tenant_id=tenant_id,
            created_ms=now_ms(),
            goal=goal,
            signals=signals,
            top_hypotheses=ranked,
            notes=(
                "llm" if self._llm is not None else "no_llm",
                "advisory_ranking_only",
                "decision_idempotent",
                "manifest_sealed",
            ),
        )

    def _persist_plan_details(
        self,
        *,
        plan: StrategyPlanV1,
        tenant_id: str,
        user_id: str,
        decision_id: str,
        correlation_id: str,
    ) -> None:
        append_strategy_snapshot(
            self._event_store,
            tenant_id=tenant_id,
            user_id=user_id,
            decision_id=decision_id,
            correlation_id=correlation_id,
            signals=plan.signals,
            goal=plan.goal,
        )
        for hypothesis in plan.top_hypotheses:
            append_hypothesis(
                self._event_store,
                tenant_id=tenant_id,
                user_id=user_id,
                decision_id=decision_id,
                correlation_id=correlation_id,
                h=hypothesis,
            )
            append_score(
                self._event_store,
                tenant_id=tenant_id,
                user_id=user_id,
                decision_id=decision_id,
                correlation_id=correlation_id,
                score=score_hypothesis(hypothesis),
            )

    def backlog(self, *, tenant_id: str, limit: int | None = None):
        backlog_limit = self._policy.default_backlog_limit if limit is None else int(limit)
        return list_backlog(self._event_store, tenant_id=str(tenant_id), limit=backlog_limit)

    def accept_hypothesis(
        self,
        *,
        tenant_id: str,
        user_id: str,
        decision_id: str,
        correlation_id: str,
        hypothesis_id: str,
        note: str = "",
    ) -> str:
        return set_hypothesis_state(
            self._event_store,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            hypothesis_id=str(hypothesis_id),
            state="accepted",
            note=str(note or ""),
        )

    def reject_hypothesis(
        self,
        *,
        tenant_id: str,
        user_id: str,
        decision_id: str,
        correlation_id: str,
        hypothesis_id: str,
        note: str = "",
    ) -> str:
        return set_hypothesis_state(
            self._event_store,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            hypothesis_id=str(hypothesis_id),
            state="rejected",
            note=str(note or ""),
        )

    def create_experiment_from_hypothesis(
        self,
        *,
        tenant_id: str,
        user_id: str,
        decision_id: str,
        correlation_id: str,
        h: GrowthHypothesisV1,
    ) -> ExperimentSpecV1:
        experiment_id = str(
            uuid.uuid5(
                _GROWTH_ID_NAMESPACE,
                f"experiment:{tenant_id}:{decision_id}:{h.hypothesis_id}",
            )
        )
        experiment = ExperimentSpecV1(
            experiment_id=experiment_id,
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
        append_experiment(
            self._event_store,
            tenant_id=str(tenant_id),
            user_id=str(user_id),
            decision_id=str(decision_id),
            correlation_id=str(correlation_id),
            exp=experiment,
        )
        return experiment


def _stable_hypothesis_id(*, tenant_id: str, decision_id: str, index: int) -> str:
    return str(
        uuid.uuid5(
            _GROWTH_ID_NAMESPACE,
            f"hypothesis:{tenant_id}:{decision_id}:{int(index)}",
        )
    )


def _stabilize_hypotheses(
    hypotheses: tuple[GrowthHypothesisV1, ...],
    *,
    tenant_id: str,
    decision_id: str,
) -> tuple[GrowthHypothesisV1, ...]:
    created_ms = now_ms()
    return tuple(
        replace(
            hypothesis,
            hypothesis_id=_stable_hypothesis_id(
                tenant_id=str(tenant_id),
                decision_id=str(decision_id),
                index=index,
            ),
            tenant_id=str(tenant_id),
            created_ms=int(hypothesis.created_ms or created_ms),
        )
        for index, hypothesis in enumerate(hypotheses)
    )


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


def _fallback_hypotheses(
    *,
    tenant_id: str,
    decision_id: str,
    signals: GrowthSignalV1,
    goal: GrowthGoalV1,
) -> tuple[GrowthHypothesisV1, ...]:
    now = int(time.time() * 1000)
    hypotheses: list[GrowthHypothesisV1] = [
        GrowthHypothesisV1(
            hypothesis_id=_stable_hypothesis_id(tenant_id=tenant_id, decision_id=decision_id, index=0),
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
        ),
        GrowthHypothesisV1(
            hypothesis_id=_stable_hypothesis_id(tenant_id=tenant_id, decision_id=decision_id, index=1),
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
        ),
    ]
    if "ads_apply_used" in set(signals.notes):
        hypotheses.append(
            GrowthHypothesisV1(
                hypothesis_id=_stable_hypothesis_id(tenant_id=tenant_id, decision_id=decision_id, index=len(hypotheses)),
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
    hypotheses.append(
        GrowthHypothesisV1(
            hypothesis_id=_stable_hypothesis_id(tenant_id=tenant_id, decision_id=decision_id, index=len(hypotheses)),
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
    return tuple(hypotheses)
