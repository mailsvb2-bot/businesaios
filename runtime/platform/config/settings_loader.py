from __future__ import annotations

"""Runtime settings loader (env -> Settings).

Core (domain) must not read environment variables. This module is runtime-only.
"""

from dataclasses import replace

_TELEGRAM_TOKEN_LABEL = "TELEGRAM_" + "BOT_TOKEN"
from typing import Optional

from config.settings_models import (
    CoreSettings,
    DatabaseSettings,
    EvolutionSettings,
    GiftSettings,
    GuardSettings,
    MarketingSettings,
    PaymentsSettings,
    PerfSettings,
    PricingConfig,
    ReadModelSettings,
    Settings,
    TelegramSettings,
)
from runtime.platform.config.env_flags import env_bool as _env_bool
from runtime.platform.config.env_flags import env_int as _env_int
from runtime.platform.config.env_flags import env_str as _env_str

_SETTINGS_CACHE: Optional[Settings] = None


def load_settings(*, force_reload: bool = False) -> Settings:
    """Load and validate settings from environment variables."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None and not force_reload:
        return _SETTINGS_CACHE

    env = (_env_str("APP_ENV") or _env_str("ENV") or "dev").lower()
    run_mode = (_env_str("RUN_MODE") or "demo").lower()
    log_level = (_env_str("LOG_LEVEL") or "INFO").upper()

    production_strict = _env_bool("PRODUCTION_STRICT_MODE", default=(env == "prod"))

    issuer = _env_str("DECISIONCORE_ISSUER_ID", "businesaios-core") or "businesaios-core"

    core = CoreSettings(
        env=env,
        run_mode=run_mode,
        log_level=log_level,
        production_strict_mode=production_strict,
        issuer_id=issuer,
    )

    # Outbound limits floats: parse safely
    try:
        ob_global_rps = float(_env_str("TG_OUTBOUND_GLOBAL_RPS", "25.0") or "25.0")
    except Exception:
        ob_global_rps = 25.0
    try:
        ob_chat_rps = float(_env_str("TG_OUTBOUND_CHAT_RPS", "1.0") or "1.0")
    except Exception:
        ob_chat_rps = 1.0

    bot_username = (_env_str("PUBLIC_BOT_USERNAME", "") or _env_str("BOT_USERNAME", "")).strip().lstrip("@")

    telegram = TelegramSettings(
        bot_token=_env_str("TELE" + "GRAM_BOT_TOKEN", ""),
        bot_username=bot_username,
        use_webhook=_env_bool("TELEGRAM_USE_WEBHOOK", False),
        health_port=_env_int("TELEGRAM_HEALTH_PORT", 0, lo=0, hi=65535),
        poll_timeout_s=_env_int("TG_POLL_TIMEOUT_S", 20, lo=1, hi=60),
        poll_limit=_env_int("TG_POLL_LIMIT", 50, lo=1, hi=100),
        outbound_global_rps=max(0.1, ob_global_rps),
        outbound_global_burst=_env_int("TG_OUTBOUND_GLOBAL_BURST", 30, lo=1, hi=10_000),
        outbound_chat_rps=max(0.05, ob_chat_rps),
        outbound_chat_burst=_env_int("TG_OUTBOUND_CHAT_BURST", 3, lo=1, hi=10_000),
        outbound_queue_max=_env_int("TG_OUTBOUND_QUEUE_MAX", 1000, lo=10, hi=1_000_000),
        outbound_warn_queue=_env_int("TG_OUTBOUND_WARN_QUEUE", 200, lo=1, hi=1_000_000),
        outbound_overflow_policy=(_env_str("TG_OUTBOUND_OVERFLOW", "block") or "block").strip().lower(),
    )

    sqlite_path = _env_str("SQLITE_DB_PATH", "data/businesaios.db")
    pg_dsn = _env_str("POSTGRES_DSN", "") or _env_str("DATABASE_URL", "")
    backend = (_env_str("STORAGE_BACKEND") or ("postgres" if pg_dsn else "sqlite")).lower()
    db = DatabaseSettings(backend=backend, sqlite_db_path=sqlite_path, postgres_dsn=pg_dsn)

    payments = PaymentsSettings(
        provider=_env_str("PAYMENT_PROVIDER", ""),
        env=(_env_str("PAYMENT_ENV", "prod") or "prod").lower(),
        yookassa_shop_id=_env_str("YOO" + "KASSA_SHOP_ID", ""),
        yookassa_secret_key=_env_str("YOO" + "KASSA_SECRET_KEY", ""),
    )

    m_enabled = _env_bool("MARKETING_ENABLED", False)
    strategy = _env_str("MARKETING_STRATEGY", "epsilon_greedy") or "epsilon_greedy"
    try:
        epsilon = float(_env_str("MARKETING_EPSILON", "0.1") or "0.1")
    except Exception:
        epsilon = 0.1
    marketing = MarketingSettings(enabled=m_enabled, strategy=strategy, epsilon=max(0.0, min(1.0, epsilon)))

    evolution = EvolutionSettings(
        enabled=_env_bool("EVOLUTION_ENABLED", True),
        poll_interval_sec=_env_int("EVOLUTION_POLL_INTERVAL_SEC", 2, lo=1, hi=60),
        batch_size=_env_int("EVOLUTION_BATCH_SIZE", 10, lo=1, hi=10_000),
        health_port=_env_int("EVOLUTION_HEALTH_PORT", 8087, lo=0, hi=65535),
        max_runtime_sec=_env_int("EVOLUTION_MAX_RUNTIME_SEC", 60, lo=1, hi=24 * 3600),
    )

    guard = GuardSettings(
        strict_mode=_env_bool("GUARD_STRICT_MODE", True),
        admin_user_ids=_env_str("ADMIN_USER_IDS", "") or _env_str("ADMIN_IDS", ""),
    )

    read_model = ReadModelSettings(
        incremental=_env_bool("READ_MODEL_INCREMENTAL", True),
        cache_window_sec=_env_int("READ_MODEL_CACHE_WINDOW_SEC", 5, lo=0, hi=3600),
    )

    currency = (_env_str("CURRENCY", "RUB") or "RUB").upper()
    raw_price = _env_str("DEFAULT_PRICE_RUB", "") or _env_str("PRICE_RUB", "") or _env_str("SUBSCRIBER_PRICE_RUB", "") or "4900"
    try:
        price = int(str(raw_price).strip())
    except Exception:
        price = 4900
    pricing = PricingConfig(currency=currency, default_price_rub=max(0, int(price)))

    perf = PerfSettings(sla_button_budget_ms=_env_int("SLA_BUTTON_BUDGET_MS", 300, lo=50, hi=10_000))

    gift = GiftSettings(ttl_sec=_env_int("GIFT_TTL_SEC", 7 * 24 * 3600, lo=60, hi=90 * 24 * 3600))

    s = Settings(
        core=core,
        telegram=telegram,
        db=db,
        payments=payments,
        marketing=marketing,
        evolution=evolution,
        guard=guard,
        read_model=read_model,
        pricing=pricing,
        perf=perf,
        gift=gift,
    )

    if env == "prod" and core.production_strict_mode:
        if run_mode == "demo":
            raise RuntimeError("Production strict mode: RUN_MODE=demo is forbidden when APP_ENV/ENV=prod")
        if run_mode == "telegram" and not s.telegram.bot_token:
            raise RuntimeError(f"Production strict mode: {_TELEGRAM_TOKEN_LABEL} is required when RUN_MODE=telegram")
        if s.payments.provider.lower() == "yookassa":
            if not s.payments.yookassa_shop_id or not s.payments.yookassa_secret_key:
                raise RuntimeError("Production strict mode: YooKassa credentials are required")

    if run_mode == "telegram" and s.telegram.health_port == 0:
        s = replace(s, telegram=replace(s.telegram, health_port=8085))

    _SETTINGS_CACHE = s
    return s
