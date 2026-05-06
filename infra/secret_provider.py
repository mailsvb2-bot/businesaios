from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvSecretProvider:
    def get_required(self, name: str) -> str:
        value = env_str(name, "") or None
        if not value:
            raise RuntimeError(f"Required secret '{name}' is missing.")
        return value

    def get_optional(self, name: str) -> str | None:
        return env_str(name, "") or None
