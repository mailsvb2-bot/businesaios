from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field


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
    paid_channels: tuple[str, ...] = (
        "meta_ads",
        "google_ads",
        "yandex_direct",
        "tiktok_ads",
        "vk_ads",
        "other_paid",
    )
    base_steps: tuple[str, ...] = (
        "Определи baseline (7 дней): метрика + сегмент/канал",
        "Сделай минимальный запуск (A/B или holdout, если возможно)",
        "Следи за guardrails (спенд, жалобы, отписки)",
        "Подведи итог и зафиксируй решение (rollout/rollback)",
    )
    paid_channel_creative_step: str = "Собери 2-3 креатива, 1 оффер, 1 посадочную/бот-цепочку"
    retention_segment_step: str = "Собери сегменты (new/active/churn-risk) и trigger-сообщения"


@dataclass(frozen=True)
class GrowthSignalsPolicy:
    event_scan_limit: int = 4000
    retention_window_days: int = 30
    retention_d1_days: int = 1
    retention_d7_days: int = 7
    percentage_multiplier: float = 100.0
    zero_ratio: float = 0.0
    top_channels_limit: int = 5
    fallback_event_limit_floor: int = 100
    fallback_event_limit_divisor: int = 8
    day_ms: int = 86_400_000
    common_event_types: tuple[str, ...] = (
        "lead_created@v1",
        "purchase_completed@v1",
        "ads_click@v1",
        "ads_impression@v1",
        "telegram_message_in@v1",
        "telegram_message_out@v1",
        "session_started@v1",
    )


DEFAULT_EXPERIMENTS_SERVICE_POLICY = ExperimentsServicePolicy()
DEFAULT_GROWTH_STRATEGY_SERVICE_POLICY = GrowthStrategyServicePolicy()
DEFAULT_GROWTH_SIGNALS_POLICY = GrowthSignalsPolicy()
