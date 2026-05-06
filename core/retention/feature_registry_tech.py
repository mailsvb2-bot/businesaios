"""Retention features: tech / quality (186–200)."""

KEYS = [
    "msg_delivery_fail_rate",
    "outbox_retry_mean",
    "outbox_retry_p90",
    "telegram_api_latency_p50",
    "telegram_api_latency_p90",
    "engine_latency_p50",
    "engine_latency_p90",
    "db_latency_p50",
    "db_latency_p90",
    "error_rate_d7",
    "crash_signal_d7",
    "timeouts_d7",
    "duplicate_event_rate",
    "idempotency_hit_rate",
    "data_freshness_score",
]
