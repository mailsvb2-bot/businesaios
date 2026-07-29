"""Neutral tenant-identity normalization contract.

This module is the single dependency-neutral owner for tenant identifier
normalization. Core, application, and runtime layers may all depend on it
without introducing an inward/outward architecture cycle.
"""

from __future__ import annotations

from typing import Any

CANON_TENANT_IDENTITY = True

_PLACEHOLDER_TENANT_IDS = frozenset({"", "default", "legacy", "none", "null"})
UNKNOWN_TENANT_ID = "unknown_tenant"


def is_placeholder_tenant_id(value: Any) -> bool:
    tenant_id = str(value or "").strip()
    return tenant_id.casefold() in _PLACEHOLDER_TENANT_IDS


def normalize_tenant_id(value: Any, *, fallback: str = "") -> str:
    tenant_id = str(value or "").strip()
    if tenant_id.casefold() in _PLACEHOLDER_TENANT_IDS:
        return str(fallback or "").strip()
    return tenant_id


def normalize_tenant_id_or_unknown(value: Any) -> str:
    return normalize_tenant_id(value) or UNKNOWN_TENANT_ID


def require_tenant_id(value: Any) -> str:
    tenant_id = normalize_tenant_id(value)
    if not tenant_id:
        raise ValueError("tenant_id is required (strict)")
    return tenant_id


def normalize_tenant_scope(value: Any, *, allow_unknown: bool = False) -> str:
    tenant_id = normalize_tenant_id(value)
    if tenant_id:
        return tenant_id
    return UNKNOWN_TENANT_ID if allow_unknown else ""


__all__ = [
    "CANON_TENANT_IDENTITY",
    "UNKNOWN_TENANT_ID",
    "is_placeholder_tenant_id",
    "normalize_tenant_id",
    "normalize_tenant_id_or_unknown",
    "normalize_tenant_scope",
    "require_tenant_id",
]
