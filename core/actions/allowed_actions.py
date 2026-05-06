from __future__ import annotations

"""Canonical allowed actions list.

Tests and security gates use this as the *single source of truth*.
Runtime registry remains the authoritative spec container.
"""

from runtime.boot.actions_registry import SPECS

ALLOWED_ACTIONS = tuple(sorted(SPECS.keys()))
