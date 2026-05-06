from __future__ import annotations

"""Thin public surface for product magic moment signals."""

from product.magic_moment.first_lead_detector import FirstLeadDetector
from product.magic_moment.magic_moment_publisher import MagicMomentPublisher

CANON_PRODUCT_MAGIC_MOMENT_SURFACE = True

__all__ = ["CANON_PRODUCT_MAGIC_MOMENT_SURFACE", "FirstLeadDetector", "MagicMomentPublisher"]
