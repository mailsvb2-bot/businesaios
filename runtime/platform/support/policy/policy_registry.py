"""Compatibility re-export of the single core policy registry."""

from __future__ import annotations

from core.ai.policy_registry import PolicyRegistry

CANON_COMPAT_SHIM = True

__all__ = ["PolicyRegistry"]
