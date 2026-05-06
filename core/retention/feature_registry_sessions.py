"""Retention features: sessions & frequency (1–20)."""

KEYS = [
    "sessions_d1",
    "sessions_d7",
    "sessions_d30",
    "active_days_d7",
    "active_days_d30",
    "session_len_mean_s",
    "session_len_p50_s",
    "session_len_p90_s",
    "session_gap_mean_s",
    "session_gap_p50_s",
    "first_action_latency_s",
    "last_action_to_exit_s",
    "night_sessions_share",
    "morning_sessions_share",
    "evening_sessions_share",
    "weekend_sessions_share",
    "return_same_day_flag",
    "return_next_day_flag",
    "streak_len_days",
    "churn_risk_proxy_gap_d",
]
