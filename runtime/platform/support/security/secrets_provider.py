from __future__ import annotations

from runtime.platform.config.env_flags import env_str


class SecretsProvider:
    def get(self, key: str, default: str | None = None) -> str | None:
        fallback = "" if default is None else str(default)
        value = env_str(key, fallback)
        if value == "" and default is None:
            return None
        return value

__all__ = [
    "SecretsProvider",
]
