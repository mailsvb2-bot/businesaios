from __future__ import annotations

from runtime.platform.config.env_flags import env_str

_ALLOWED_MODES = {"webhook", "smtp", "configured_noop"}


def read_mode(prefix: str, *, default: str) -> str:
    value = env_str(f"{prefix}_MODE", "").lower()
    if value in _ALLOWED_MODES:
        return value
    return str(default)


def token_present(prefix: str) -> bool:
    return bool(
        env_str(f"{prefix}_TOKEN", "")
        or env_str(f"{prefix}_API_KEY", "")
        or env_str(f"{prefix}_ACCESS_TOKEN", "")
    )
