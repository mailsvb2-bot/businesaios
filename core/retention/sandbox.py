from __future__ import annotations

from config.env_flags import env_bool, env_csv


def _csv_set(items: list[str]) -> set[str]:
    return {item.strip() for item in items if item and item.strip()}


def retention_sandbox_enabled() -> bool:
    return env_bool("RETENTION_SANDBOX", False)


def retention_allowed_user_ids() -> set[str]:
    # Comma-separated user ids, e.g. "u123,u456"
    return _csv_set(env_csv("RETENTION_SANDBOX_USER_IDS", ""))


def retention_is_allowed(user_id: str) -> bool:
    if not retention_sandbox_enabled():
        return True
    allow = retention_allowed_user_ids()
    # Sandbox ON + empty allowlist => allow nobody (safe).
    if not allow:
        return False
    return str(user_id) in allow
