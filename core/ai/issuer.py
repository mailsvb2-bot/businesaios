from __future__ import annotations

"""Issuer utilities.

This module is security-critical for envelope governance.

Responsibilities:
- Stable issuer_id for envelope origin pinning.
- Centralized production safety checks for signing secrets.
  (No default secrets in production.)
"""


def issuer_id(*, value: str | None = None) -> str:
    """Stable issuer id for envelope origin pinning.

    This does not replace cryptographic signatures; it prevents accidental cross-core
    envelope reuse when multiple deployments share keys.
    """

    return (str(value).strip() if value is not None and str(value).strip() else "businesaios-core")


def require_signing_secret_is_safe(*, env: str, secret_raw: str) -> None:
    """Enforce that production deployments never use a default/empty secret."""
    env = (env or "dev").lower()
    if env in {"prod", "production"} and (not secret_raw or secret_raw.strip() in {"dev-secret", "change-me", "default"}):
        raise RuntimeError("DECISION_SIGNING_SECRET must be set to a non-default value in production")
