"""Closed mapping of Telegram administrative read projections to the existing event store.

This is a contract, not an alternative policy, executor or data owner.
"""
from __future__ import annotations

ADMIN_ANALYTICS_ROUTES = frozenset({
    "admin:segments",
    "admin:ab",
    "admin:giftshare",
    "admin:funnel2",
})
