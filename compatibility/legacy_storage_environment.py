"""Data-only catalog of retired storage environment aliases.

This module is the sole migration owner for historical deployment variable
names. Runtime and CI surfaces consume the catalog but never embed legacy
product identities themselves.
"""

from __future__ import annotations

LEGACY_STORAGE_ENV_KEYS = (
    "METRO_DB_ENGINE",
    "STORAGE_DB_ENGINE",
    "METRO_DATABASE_URL",
    "METRO_POSTGRES_DSN",
)

__all__ = ["LEGACY_STORAGE_ENV_KEYS"]
