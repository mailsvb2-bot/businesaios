"""Retention module (thin init).

CRITICAL:
Do NOT import connector layer / offer catalogs here.
This package must be safe to import from anywhere, including OfferEngine layer.
"""

from .engine import RetentionEngine

__all__ = ["RetentionEngine"]

# NOTE:
# External connectors are intentionally not imported here.
# Import explicitly where needed:
#   use core.retention.decision_adapter.RetentionDecisionAdapter
