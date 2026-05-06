from __future__ import annotations

from runtime.platform.config.env_flags import env_str

from .token_store import SecretVault


class EnvSecretVault(SecretVault):
    """Environment variable backed secrets.

    Safe default for local/dev. In production, replace with a KMS adapter.
    """

    def get_secret(self, key: str) -> str:
        v = env_str(key, "")
        if not v:
            raise KeyError(f"Missing secret: {key}")
        return v
