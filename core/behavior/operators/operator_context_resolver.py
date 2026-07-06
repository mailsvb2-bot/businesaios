from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.behavior.operators.operator_runtime_context import OperatorRuntimeContext
from core.tenancy.normalization import normalize_tenant_id


def resolve_operator_runtime_context(payload: Mapping[str, Any]) -> OperatorRuntimeContext:
    return OperatorRuntimeContext(
        tenant_id=normalize_tenant_id(payload.get("tenant_id")) or None,
        product=_string_or_none(payload.get("product")),
        env=_string_or_none(payload.get("env")),
        domain=_string_or_none(payload.get("domain")),
        channel=_string_or_none(payload.get("channel")),
        funnel_stage=_string_or_none(payload.get("funnel_stage")),
        actor_role=_string_or_none(payload.get("actor_role")),
        safe_mode=bool(payload.get("safe_mode", False)),
        operator_catalog_ref=_catalog_ref_or_default(payload.get("operator_catalog_ref")),
        operator_policy_catalog_ref=_string_or_none(payload.get("operator_policy_catalog_ref")),
        operator_overrides=payload.get("operator_overrides", {}) or {},
    )


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _catalog_ref_or_default(value: Any) -> str:
    text = str(value or "").strip()
    return text or "default"
