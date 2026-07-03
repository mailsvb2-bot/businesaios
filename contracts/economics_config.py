"""Canonical economics config contract.

This module is the contract-facing import point for product contracts and product
loading. It keeps the contracts layer from importing a concrete core namespace
directly, while preserving the existing EconomicsConfigV1 implementation and
serialization semantics.
"""

from __future__ import annotations

from core.economics.economics_config import EconomicsConfigV1

__all__ = ["EconomicsConfigV1"]
