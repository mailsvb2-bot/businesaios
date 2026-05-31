from __future__ import annotations

from dataclasses import dataclass

CANON_COMPAT_SHIM = True

@dataclass(frozen=True)
class CoreSettings:
    env: str = "dev"
    issuer_id: str = "businesaios-core"
    run_mode: str = "demo"
    log_level: str = "INFO"
    production_strict_mode: bool = False


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str = ""
    bot_username: str = ""
    use_webhook: bool = False
    health_port: int = 0
    poll_timeout_s: int = 20
    poll_limit: int = 50
    outbound_global_rps: float = 25.0
    outbound_global_burst: int = 30
    outbound_chat_rps: float = 1.0
    outbound_chat_burst: int = 3
    outbound_queue_max: int = 1000
    outbound_warn_queue: int = 200
    outbound_overflow_policy: str = "block"


@dataclass(frozen=True)
class DatabaseSettings:
    backend: str = "sqlite"
    sqlite_db_path: str = "data/businesaios.db"
    postgres_dsn: str = ""


@dataclass(frozen=True)
class PaymentsSettings:
    provider: str = ""
    env: str = "prod"
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""


@dataclass(frozen=True)
class MarketingSettings:
    enabled: bool = False
    strategy: str = "epsilon_greedy"
    epsilon: float = 0.1


@dataclass(frozen=True)
class EvolutionSettings:
    enabled: bool = True
    poll_interval_sec: int = 2
    batch_size: int = 10
    health_port: int = 8087
    max_runtime_sec: int = 60


@dataclass(frozen=True)
class GuardSettings:
    strict_mode: bool = True
    admin_user_ids: str = ""


@dataclass(frozen=True)
class ReadModelSettings:
    incremental: bool = True
    cache_window_sec: int = 5


@dataclass(frozen=True)
class PricingConfig:
    currency: str = "RUB"
    default_price_rub: int = 4900


@dataclass(frozen=True)
class PerfSettings:
    sla_button_budget_ms: int = 300


@dataclass(frozen=True)
class GiftSettings:
    ttl_sec: int = 7 * 24 * 3600


@dataclass(frozen=True)
class Settings:
    core: CoreSettings
    telegram: TelegramSettings
    db: DatabaseSettings
    payments: PaymentsSettings
    marketing: MarketingSettings
    evolution: EvolutionSettings
    guard: GuardSettings
    read_model: ReadModelSettings
    pricing: PricingConfig
    perf: PerfSettings
    gift: GiftSettings
