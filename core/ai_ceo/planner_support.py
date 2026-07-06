from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from core._safe_logging import log_fallback
from core.ai_ceo.contracts import CEOIntentV1, CEOPlanStepV1, CEOPlanV1
from core.ai_ceo.intent import build_intent_from_session_args
from core.ai_ceo.ledger import GrowthSnapshotV1
from core.ai_ceo.ledger import to_dict as snapshot_to_dict
from core.ai_ceo.safety import AutonomyPolicyV1, check_step_allowed
from core.ai_ceo.scoring import rank_steps
from kernel.world_state import WorldStateV1

logger = logging.getLogger(__name__)


class CEOContextReader:
    @staticmethod
    def safe_locale(state: WorldStateV1) -> str:
        try:
            session = state.session or {}
            user = state.user or {}
            locale = str(session.get("locale") or user.get("locale") or "ru").strip()
            return locale or "ru"
        except (AttributeError, TypeError, ValueError) as exc:
            log_fallback(logger, event="ai_ceo.safe_locale", error=exc)
            return "ru"

    @staticmethod
    def safe_channel(state: WorldStateV1) -> str:
        try:
            session = state.session or {}
            meta = state.meta or {}
            channel = str(session.get("channel") or meta.get("channel") or "telegram").strip()
            return channel or "telegram"
        except (AttributeError, TypeError, ValueError) as exc:
            log_fallback(logger, event="ai_ceo.safe_channel", error=exc)
            return "telegram"

    @staticmethod
    def safe_offer(state: WorldStateV1) -> dict[str, Any]:
        try:
            product = state.product if isinstance(state.product, dict) else {}
            offer = product.get("default_offer")
            if isinstance(offer, dict) and offer:
                return dict(offer)
        except (AttributeError, TypeError, ValueError) as exc:
            log_fallback(logger, event="ai_ceo.safe_offer", error=exc)
        return {
            "offer_id": "profit_sprint_default",
            "title": "Profit Sprint",
            "price_minor": 0,
            "currency": "RUB",
        }

    @staticmethod
    def safe_user_id(state: WorldStateV1) -> str:
        return str(getattr(state, "user_id", None) or (state.user or {}).get("user_id") or "unknown")

    @staticmethod
    def default_intent_from_state(state: WorldStateV1) -> CEOIntentV1:
        session = state.session or {}
        return build_intent_from_session_args(
            args=session.get("args"),
            objective=str(session.get("objective") or "increase_profit"),
        )


def _build_blocked_step(step: CEOPlanStepV1, *, autonomy: AutonomyPolicyV1, snapshot: GrowthSnapshotV1) -> CEOPlanStepV1:
    user_id = str(getattr(snapshot, "user_id", "") or "system")
    reason = check_step_allowed(step.action, policy=autonomy)
    payload = {
        "user_id": user_id,
        "text": f"🛑 AI CEO: шаг '{step.title}' заблокирован политикой ({reason}).",
        "track_event_type": "ai_ceo_blocked_step",
        "track_payload": {
            "source": "ai_ceo",
            "blocked_action": str(step.action),
            "blocked_title": str(step.title),
            "blocked_reason": str(reason or "policy"),
        },
    }
    original_payload = dict(step.payload or {})
    track_payload = original_payload.get("track_payload")
    track_payload = dict(track_payload) if isinstance(track_payload, dict) else {}
    tenant_id = str(original_payload.get("tenant_id") or track_payload.get("tenant_id") or "").strip()
    plan_id = str(track_payload.get("plan_id") or "").strip()
    if tenant_id:
        payload["track_payload"]["tenant_id"] = tenant_id
    if plan_id:
        payload["track_payload"]["plan_id"] = plan_id
    return replace(step, action="send_message@v1", payload=payload, tags=tuple(list(step.tags) + ["blocked"]))


def build_default_plan_steps(*, tenant_id: str, user_id: str, locale: str, channel: str, offer: dict[str, Any], plan_id: str, dry_run: bool) -> list[CEOPlanStepV1]:
    safe_tenant = str(tenant_id or "unknown")
    safe_user = str(user_id or "unknown")
    safe_locale = str(locale or "ru")
    safe_channel = str(channel or "telegram")
    safe_offer = dict(offer or {})
    track_base = {"source": "ai_ceo", "tenant_id": safe_tenant, "plan_id": plan_id}
    return [
        CEOPlanStepV1(
            title="Запустить Profit Sprint",
            rationale="Автопилот соберёт базовые данные и предложит быстрые действия для роста прибыли.",
            action="one_click_value@v1",
            payload={
                "tenant_id": safe_tenant,
                "user_id": safe_user,
                "locale": safe_locale,
                "channel": safe_channel,
                "offer": safe_offer,
                "track_event_type": "ai_ceo_profit_sprint",
                "track_payload": dict(track_base),
            },
            tags=("autopilot", "low_risk"),
        ),
        CEOPlanStepV1(
            title="Открыть обзор цены",
            rationale="AI подготовит контекст для изменения цены; само изменение остаётся отдельным подтверждаемым действием.",
            action="send_message@v1",
            payload={
                "user_id": safe_user,
                "text": "💸 AI CEO: откройте Pricing → Review, чтобы посмотреть рекомендованную цену и применить её с подтверждением.",
                "track_event_type": "ai_ceo_pricing_review_prompt",
                "track_payload": dict(track_base),
            },
            tags=("pricing", "review_first"),
        ),
        CEOPlanStepV1(
            title="Открыть Ads Apply",
            rationale="Подготовим запуск рекламы через preview/confirm с лимитами и kill-switch.",
            action="send_message@v1",
            payload={
                "user_id": safe_user,
                "text": "📣 AI CEO: откройте Ads Apply → Preview → Confirm. Запуск идёт только через защищённый runtime-контракт.",
                "track_event_type": "ai_ceo_ads_apply_prompt",
                "track_payload": {**track_base, "mode": "dry_run" if dry_run else "guarded"},
            },
            tags=("ads", "ui_first"),
        ),
    ]


class CEOPlanBuilder:
    def __init__(self, *, state: WorldStateV1, autonomy: AutonomyPolicyV1, plan_id: str) -> None:
        self._state = state
        self._autonomy = autonomy
        self._plan_id = plan_id
        self._tenant_id = str(getattr(state, "tenant_id", "") or "unknown")
        self._user_id = CEOContextReader.safe_user_id(state)

    def build_steps(self) -> list[CEOPlanStepV1]:
        return build_default_plan_steps(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            locale=CEOContextReader.safe_locale(self._state),
            channel=CEOContextReader.safe_channel(self._state),
            offer=CEOContextReader.safe_offer(self._state),
            plan_id=self._plan_id,
            dry_run=bool(self._autonomy.dry_run),
        )


def apply_policy_and_rank(
    *,
    steps: Iterable[CEOPlanStepV1],
    autonomy: AutonomyPolicyV1,
    snapshot: GrowthSnapshotV1,
) -> list[CEOPlanStepV1]:
    safe_steps: list[CEOPlanStepV1] = []
    for step in steps:
        reason = check_step_allowed(step.action, policy=autonomy)
        if reason:
            safe_steps.append(_build_blocked_step(step, autonomy=autonomy, snapshot=snapshot))
        else:
            safe_steps.append(step)
    try:
        ranked = rank_steps(steps=safe_steps, snapshot=snapshot)
        return [step for (step, _score) in ranked]
    except (AttributeError, TypeError, ValueError) as exc:
        log_fallback(logger, event="ai_ceo.apply_policy_and_rank", error=exc)
        return list(safe_steps)


def build_plan_targets(*, intent: CEOIntentV1) -> dict[str, Any]:
    return {
        "horizon_days": intent.horizon_days,
        "risk_level": intent.risk_level,
        "profit_delta_minor": intent.target_profit_delta_minor,
    }


def build_plan_summary() -> str:
    return "AI CEO план: 3 шага для роста прибыли. По умолчанию всё в безопасном режиме (dry-run/подтверждение)."


def render_plan_text(plan: CEOPlanV1, *, currency: str = "₽") -> str:
    metrics = plan.kpi_before or {}
    profit = int(metrics.get("profit_minor", 0))
    spend = int(metrics.get("spend_minor", 0))
    revenue = int(metrics.get("revenue_minor", 0))
    leads = int(metrics.get("leads", 0))
    lines = [
        "🧠 AI CEO — план действий",
        "",
        f"Сегодня: лиды={leads}, выручка={revenue}{currency}, расход={spend}{currency}, прибыль={profit}{currency}",
        f"Горизонт: {plan.intent.horizon_days} дн. Риск: {plan.intent.risk_level}",
        "",
        plan.summary,
        "",
    ]
    for index, step in enumerate(plan.steps, start=1):
        lines.append(f"{index}) {step.title}")
        if step.rationale:
            lines.append(f"   • {step.rationale}")
        if step.tags:
            lines.append(f"   • теги: {', '.join([str(tag) for tag in step.tags])}")
    lines.extend(["", "⚠️ Выполнение требует подтверждения (в меню)."])
    return "\n".join(lines)


def build_plan(
    state: WorldStateV1,
    *,
    autonomy: AutonomyPolicyV1,
    snapshot: GrowthSnapshotV1,
    intent: CEOIntentV1 | None = None,
    plan_id: str = "ai_ceo_plan",
) -> CEOPlanV1:
    used_intent = intent or CEOContextReader.default_intent_from_state(state)
    resolved_plan_id = str(plan_id).strip() or "ai_ceo_plan"
    builder = CEOPlanBuilder(state=state, autonomy=autonomy, plan_id=resolved_plan_id)
    raw_steps = builder.build_steps()
    final_steps = apply_policy_and_rank(
        steps=raw_steps,
        autonomy=autonomy,
        snapshot=snapshot,
    )
    return CEOPlanV1(
        plan_id=resolved_plan_id,
        intent=used_intent,
        summary=build_plan_summary(),
        steps=final_steps,
        kpi_before=snapshot_to_dict(snapshot),
        kpi_targets=build_plan_targets(intent=used_intent),
    )
