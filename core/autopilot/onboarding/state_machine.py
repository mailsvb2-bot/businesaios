from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional
from collections.abc import Mapping

from core.observability.structured_logging import log_exception_throttled

from .schema import (
    BudgetChoice,
    Diagnostics,
    HasClientsChoice,
    budget_choice_to_minor,
    parse_int_from_text,
    rub_to_minor,
)
from .state_machine_support import (
    build_ads_connect_keyboard,
    build_budget_keyboard,
    build_has_clients_keyboard,
    transition,
)


class OnboardingStep(str, Enum):
    DIAG_WHAT = "diag:what"
    DIAG_AVG_CHECK = "diag:avg_check"
    DIAG_MARGIN = "diag:margin"
    DIAG_REGION = "diag:region"
    DIAG_HAS_CLIENTS = "diag:has_clients"
    BUDGET_7D = "budget:7d"
    PICK_OFFER = "pick:offer"
    PICK_CHANNEL = "pick:channel"
    CONNECT_ADS = "ads:connect"
    READY_LAUNCH = "ready:launch"
    RUNNING = "running"
    AUDIT_STOP_LOSS = "audit:stop_loss"


@dataclass(frozen=True)
class OnboardingSession:
    stage: OnboardingStep
    goal: str
    diag: Diagnostics
    offer_id: str = ""
    channel: str = "internal"
    ads_platform: str = ""
    tasks: list[dict] | None = None

    def to_settings(self) -> dict[str, Any]:
        return {
            "stage": str(self.stage.value),
            "goal": str(self.goal),
            "diag": self.diag.to_dict(),
            "offer_id": str(self.offer_id),
            "channel": str(self.channel),
            "ads_platform": str(self.ads_platform),
            "tasks": list(self.tasks or []),
        }

    @staticmethod
    def from_settings(d: Mapping[str, Any] | None) -> OnboardingSession:
        d = dict(d or {})
        try:
            stage = OnboardingStep(str(d.get("stage") or OnboardingStep.DIAG_WHAT.value))
        except Exception:
            stage = OnboardingStep.DIAG_WHAT
        return OnboardingSession(
            stage=stage,
            goal=str(d.get("goal") or "profit_7d"),
            diag=Diagnostics.from_dict(d.get("diag") if isinstance(d.get("diag"), dict) else {}),
            offer_id=str(d.get("offer_id") or ""),
            channel=str(d.get("channel") or "internal"),
            ads_platform=str(d.get("ads_platform") or ""),
            tasks=list(d.get("tasks") or []) if isinstance(d.get("tasks"), list) else None,
        )


@dataclass(frozen=True)
class OnboardingTransition:
    session: OnboardingSession
    notify_text: str
    reply_markup: dict | None
    use_callback_query_id: bool = False


def session_from_settings(settings: Mapping[str, Any] | None) -> OnboardingSession:
    try:
        if isinstance(settings, dict):
            return OnboardingSession.from_settings(settings.get("autopilot:session") or {})
    except Exception as exc:
        log_exception_throttled(__name__, "autopilot_onboarding_session_from_settings_failed", exc)
    return OnboardingSession(stage=OnboardingStep.DIAG_WHAT, goal="profit_7d", diag=Diagnostics(), ads_platform="")


def session_to_settings(sess: OnboardingSession) -> dict[str, Any]:
    return {"autopilot:session": sess.to_settings()}


def advance_with_text(sess: OnboardingSession, text: str) -> OnboardingTransition | None:
    t = (text or "").strip()
    if not t:
        return None

    d = sess.diag
    stage = sess.stage

    if stage == OnboardingStep.DIAG_WHAT:
        d2 = Diagnostics(**{**d.__dict__, "what": t[:200]})
        return transition(session_cls=OnboardingSession, transition_cls=OnboardingTransition, sess=sess, stage=OnboardingStep.DIAG_AVG_CHECK, diag=d2, notify_text="2) Средний чек (в ₽, число)?", reply_markup=None)

    if stage == OnboardingStep.DIAG_AVG_CHECK:
        rub = parse_int_from_text(t)
        d2 = Diagnostics(**{**d.__dict__, "avg_check_minor": rub_to_minor(rub), "currency": "RUB"})
        return transition(session_cls=OnboardingSession, transition_cls=OnboardingTransition, sess=sess, stage=OnboardingStep.DIAG_MARGIN, diag=d2, notify_text="3) Маржа (%) примерно?", reply_markup=None)

    if stage == OnboardingStep.DIAG_MARGIN:
        pct = parse_int_from_text(t)
        d2 = Diagnostics(**{**d.__dict__, "margin_pct": int(pct)})
        return transition(session_cls=OnboardingSession, transition_cls=OnboardingTransition, sess=sess, stage=OnboardingStep.DIAG_REGION, diag=d2, notify_text="4) Регион (город/страна) — где вы продаёте?", reply_markup=None)

    if stage == OnboardingStep.DIAG_REGION:
        d2 = Diagnostics(**{**d.__dict__, "region": t[:64]})
        return transition(
            session_cls=OnboardingSession,
            transition_cls=OnboardingTransition,
            sess=sess,
            stage=OnboardingStep.DIAG_HAS_CLIENTS,
            diag=d2,
            notify_text="5) У вас уже есть клиенты/продажи?",
            reply_markup=build_has_clients_keyboard(),
        )

    return None


def advance_with_callback(sess: OnboardingSession, callback_data: str) -> OnboardingTransition | None:
    cb = str(callback_data or "")
    d = sess.diag

    if cb.startswith("autopilot:has_clients:"):
        v = cb.split(":", 2)[2].strip()
        try:
            hc = HasClientsChoice(v)
        except Exception:
            hc = HasClientsChoice.UNKNOWN
        d2 = Diagnostics(**{**d.__dict__, "has_clients": hc})
        return transition(
            session_cls=OnboardingSession,
            transition_cls=OnboardingTransition,
            sess=sess,
            stage=OnboardingStep.BUDGET_7D,
            diag=d2,
            notify_text="Экран 2/4 — Сколько готовы инвестировать на тест (7 дней)?",
            reply_markup=build_budget_keyboard(),
            use_callback_query_id=True,
        )

    if cb.startswith("autopilot:budget:"):
        v = cb.split(":", 2)[2].strip()
        try:
            bc = BudgetChoice(v)
        except Exception:
            bc = BudgetChoice.EUR_300
        minor, cur = budget_choice_to_minor(bc)
        d2 = Diagnostics(**{**d.__dict__, "budget_minor_7d": int(minor), "budget_currency": str(cur)})
        return transition(
            session_cls=OnboardingSession,
            transition_cls=OnboardingTransition,
            sess=sess,
            stage=OnboardingStep.PICK_OFFER,
            diag=d2,
            notify_text="Шаг 1/4 — Выбери оффер (из каталога):",
            reply_markup=None,
            use_callback_query_id=True,
        )

    if cb.startswith("autopilot:pick_channel:"):
        ch = cb.split(":", 2)[2].strip()
        next_channel = "external" if ch == "external" else "internal"
        if next_channel == "external":
            return transition(
                session_cls=OnboardingSession,
                transition_cls=OnboardingTransition,
                sess=sess,
                stage=OnboardingStep.CONNECT_ADS,
                channel=next_channel,
                notify_text="Экран 3/4 — Подключение рекламы\n\nВыбери платформу (OAuth, 3 клика):",
                reply_markup=build_ads_connect_keyboard(),
                use_callback_query_id=True,
            )
        return transition(
            session_cls=OnboardingSession,
            transition_cls=OnboardingTransition,
            sess=sess,
            stage=OnboardingStep.READY_LAUNCH,
            channel=next_channel,
            notify_text="Шаг 3/4 — Запуск\n\nНажми ‘Запустить’, и я начну измерять и предлагать улучшения.",
            reply_markup=None,
            use_callback_query_id=True,
        )

    if cb.startswith("autopilot:ads_connect:"):
        platform = cb.split(":", 2)[2].strip()
        return transition(
            session_cls=OnboardingSession,
            transition_cls=OnboardingTransition,
            sess=sess,
            stage=OnboardingStep.READY_LAUNCH,
            ads_platform=platform,
            notify_text=f"Ок. Подключаем {platform}. Сейчас пришлю ссылку OAuth и затем можно запускать.",
            reply_markup=None,
            use_callback_query_id=True,
        )

    return None
