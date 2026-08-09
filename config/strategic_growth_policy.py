from __future__ import annotations

import re
from dataclasses import dataclass

CANON_COMPAT_SHIM = True


@dataclass(frozen=True)
class ExperimentsServicePolicy:
    zero_metric_value: float = 0.0
    legacy_snapshot_value: float = 0.0
    legacy_uplift: float = 0.0
    legacy_p_value: float = 1.0


@dataclass(frozen=True)
class GrowthStrategyServicePolicy:
    zero_rank_score: float = 0.0
    default_backlog_limit: int = 50
    default_hypothesis_count: int = 8
    default_duration_days: int = 14
    max_experiment_name_length: int = 120
    partnership_trigger_terms: tuple[str, ...] = ("partner", "партнер", "партнёр", "referral", "реферал", "без платной рекламы", "zero paid")
    paid_channels: tuple[str, ...] = ("meta_ads", "google_ads", "yandex_direct", "tiktok_ads", "vk_ads", "other_paid")
    base_steps: tuple[str, ...] = ("Определи baseline (7 дней): метрика + сегмент/канал", "Сделай минимальный запуск (A/B или holdout, если возможно)", "Следи за guardrails (спенд, жалобы, отписки)", "Подведи итог и зафиксируй решение (rollout/rollback)")
    paid_channel_creative_step: str = "Собери 2-3 креатива, 1 оффер, 1 посадочную/бот-цепочку"
    retention_segment_step: str = "Собери сегменты (new/active/churn-risk) и trigger-сообщения"

    @staticmethod
    def _constraint_text(constraints: tuple[str, ...]) -> str:
        return " ".join(str(item or "").strip().casefold() for item in constraints)

    def partnership_constraints_exclude(self, constraints: tuple[str, ...]) -> bool:
        text = self._constraint_text(constraints)
        return re.search(r"(?:\b(?:no|without|exclude)\s+(?:paid\s+)?partner\w*|(?:без|исключить)\s+(?:платн\w+\s+)?партн[её]р\w*|не\s+использовать\s+партн[её]р\w*|партн[её]р\w*\s+не\s+использовать)", text) is not None

    def partnership_constraints_match(self, constraints: tuple[str, ...]) -> bool:
        text = self._constraint_text(constraints)
        zero_budget = re.search(r"(?<!\w)(?:budget|бюджет)\s*(?:(?:[:=])\s*)?0(?:[.,]0+)?(?![\d.,])", text) is not None
        return zero_budget or any(term in text for term in self.partnership_trigger_terms)


@dataclass(frozen=True)
class GrowthSignalsPolicy:
    event_scan_limit: int = 4000
    retention_window_days: int = 30
    retention_d1_days: int = 1
    retention_d7_days: int = 7
    sales_funnel_window_days: int = 30
    percentage_multiplier: float = 100.0
    zero_ratio: float = 0.0
    top_channels_limit: int = 5
    fallback_event_limit_floor: int = 100
    fallback_event_limit_divisor: int = 8
    day_ms: int = 86_400_000
    common_event_types: tuple[str, ...] = ("lead_created@v1", "purchase_completed@v1", "ads_click@v1", "ads_impression@v1", "telegram_message_in@v1", "telegram_message_out@v1", "session_started@v1")


DEFAULT_EXPERIMENTS_SERVICE_POLICY = ExperimentsServicePolicy()
DEFAULT_GROWTH_STRATEGY_SERVICE_POLICY = GrowthStrategyServicePolicy()
DEFAULT_GROWTH_SIGNALS_POLICY = GrowthSignalsPolicy()
