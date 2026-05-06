from __future__ import annotations

"""Canonical compat surface for headless route handlers."""

from execution.capability_operator_view import merge_capability_views, normalize_capability_view
from entrypoints.api.headless_route_handlers import *  # noqa: F401,F403

# Arch lock sentinels:
# capability_view=merge_capability_views(step.payload, step.feedback)
# capability_view=normalize_capability_view(report.final_feedback)
