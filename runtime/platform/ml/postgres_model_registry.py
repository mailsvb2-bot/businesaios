from __future__ import annotations

"""DEPRECATED Postgres backend (disabled by System TZ).

System TZ requires: all real integrations only through runtime/_internal/_effects_impl.py.

This repository's canonical production build uses SQLite backends. This module remains
only to keep import paths stable; it contains NO DB driver imports and NO integration code.
"""

from typing import Any


class PostgresModelRegistry:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError(
            "Postgres backend is disabled in this build per System TZ. "
            "Use SQLite backend (recommended), or re-implement Postgres integration "
            "inside runtime/_internal/_effects_impl.py."
        )
