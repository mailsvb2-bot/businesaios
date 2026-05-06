from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, Any

from config.revenue_report_policy import DEFAULT_REVENUE_REPORT_POLICY, RevenueReportPolicy
from core.contracts.revenue_report import RevenueReport
from core.analytics.revenue_metrics import EventStore, make_yesterday_window, aggregate_revenue_metrics
from core.analytics.roi_estimator import SimpleROIEstimator


class OfferAutopilot(Protocol):
    def decide_next_offer(self, *, tenant_id: str, world: dict) -> Any: ...


@dataclass
class RevenueReporter:
    store: EventStore
    autopilot: OfferAutopilot
    roi: SimpleROIEstimator = field(default_factory=SimpleROIEstimator)
    policy: RevenueReportPolicy = DEFAULT_REVENUE_REPORT_POLICY

    def build_daily_report(self, *, tenant_id: str, now_utc: datetime | None = None) -> RevenueReport:
        now_utc = (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
        window = make_yesterday_window(now_utc)
        events = self.store.latest_events(tenant_id=tenant_id, limit=self.policy.latest_events_limit)
        m = aggregate_revenue_metrics(events=events, window=window)

        impressions = int(m["impressions"])
        ctr = float(m["ctr"])
        cr = float(m["cr"])
        baseline_rev = float(m["revenue"])
        action_key = self.policy.default_action_key

        if impressions < self.policy.minimum_impressions_for_autopilot:
            nba_title = "Увеличить охват (показы)"
            nba_text = (
                "Сейчас слишком мало показов, чтобы Autopilot уверенно улучшал выручку.\n"
                "Действие на сегодня: включи 1 дополнительный слот показа оффера (ещё 1 сообщение в день) "
                "или добавь ещё один входной триггер (например, после прослушивания/после меню)."
            )
            action_key = self.policy.increase_impressions_action_key
        elif ctr < self.policy.ctr_threshold:
            nba_title = "Поднять CTR (кликабельность)"
            nba_text = (
                "CTR низкий — людям не цепляет первый экран.\n"
                "Действие на сегодня: поменяй 1-ю строку оффера на более конкретный эффект + меньше риска.\n"
                "Шаблон: «За 7 дней: <эффект>. Если не почувствуешь — верну деньги»."
            )
            action_key = self.policy.improve_ctr_action_key
        elif cr < self.policy.cr_threshold:
            nba_title = "Поднять CR (конверсию в оплату)"
            nba_text = (
                "Кликают, но не покупают — барьер риска/доверия.\n"
                "Действие на сегодня: добавь гарантию/соц.доказательства/лимит по времени.\n"
                "Шаблон: «Гарантия 7 дней», «200+ отзывов», «Цена до завтра»."
            )
            action_key = self.policy.improve_cr_action_key
        else:
            nba_title = "Удвоить лучший оффер"
            nba_text = (
                "Показатели уже неплохие. Действие на сегодня: увеличить долю показов лучшего оффера "
                "и добавить 1 вариацию (A/B) только по заголовку."
            )
            action_key = "double_winner"

        roi = self.roi.estimate(
            baseline_revenue=baseline_rev,
            action=action_key,
            impressions=impressions,
            clicks=int(m["clicks"]),
        )
        nba_text = (
            nba_text
            + "\n\n"
            + f"💡 Оценка эффекта: +{roi.expected_delta_revenue:.2f} (≈ {_pct(roi.expected_uplift_pct, policy=self.policy)}), "
            + f"уверенность {int(roi.confidence*100)}%."
        )

        return RevenueReport(
            day=window.day,
            impressions=impressions,
            clicks=int(m["clicks"]),
            purchases_success=int(m["purchases_success"]),
            purchases_failed=int(m["purchases_failed"]),
            revenue=float(m["revenue"]),
            ctr=ctr,
            cr=cr,
            arpu=float(m["arpu"]),
            top_offer_id=m["top_offer_id"],
            top_offer_revenue=float(m["top_offer_revenue"]),
            next_best_action_title=nba_title,
            next_best_action_text=nba_text,
        )


def _pct(x: float, *, policy: RevenueReportPolicy = DEFAULT_REVENUE_REPORT_POLICY) -> str:
    return f"{x * policy.uplift_percent_multiplier:.1f}%"
