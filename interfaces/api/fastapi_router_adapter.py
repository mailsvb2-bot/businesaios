"""Canonical compat surface for the FastAPI router adapter.

This file intentionally contains no hard-coded secrets and delegates to the
single owner implementation in adapters.api.fastapi.router_adapter.
"""

from __future__ import annotations

from adapters.api.fastapi.router_adapter import *  # noqa: F401,F403

