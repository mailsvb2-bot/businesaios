from __future__ import annotations

"""Canonical compat surface for admin route handlers."""

from application.capability.capability_operator_view import normalize_capability_view
from entrypoints.api.admin_route_handlers import *  # noqa: F401,F403

# Arch lock sentinel: normalize_capability_view(capability_view)
