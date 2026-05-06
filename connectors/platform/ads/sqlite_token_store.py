from __future__ import annotations

"""SQLite token store owner for Ads connectors.

This module stays as the canonical platform-facing owner. Raw sqlite usage remains
in runtime/platform/outbox/ads_token_store_sqlite.py; this file adds validation and
redacted diagnostics without duplicating persistence logic.
"""

from pathlib import Path
from typing import Any

from runtime.platform.outbox.ads_token_store_sqlite import SqliteAdsTokenStore as _RuntimeSqliteAdsTokenStore


class SqliteAdsTokenStore(_RuntimeSqliteAdsTokenStore):
    def __init__(self, db_path: str | Path):
        path = Path(db_path)
        if path.exists() and path.is_dir():
            raise ValueError('db_path must be a file path, not a directory')
        parent = path.parent
        if str(parent) not in {'', '.'}:
            parent.mkdir(parents=True, exist_ok=True)
        super().__init__(path)
        self._validated_path = path

    @property
    def db_path(self) -> str:
        return str(self._validated_path)

    def snapshot(self) -> dict[str, Any]:
        return {
            'db_path': self.db_path,
            'exists': self._validated_path.exists(),
            'size_bytes': self._validated_path.stat().st_size if self._validated_path.exists() else 0,
            'backend': 'sqlite',
        }


__all__ = ['SqliteAdsTokenStore']
