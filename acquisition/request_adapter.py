from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .feasibility_solver import AcquisitionFeasibilityRequest
from .funnel_model import FunnelStage
from shared.numbers import coerce_float, coerce_int

CANON_ACQUISITION_REQUEST_ADAPTER = True


class AcquisitionPayloadError(ValueError):
    """Raised when an external payload violates the canonical acquisition contract."""


def request_from_payload(
    payload: Mapping[str, Any] | AcquisitionFeasibilityRequest,
) -> AcquisitionFeasibilityRequest:
    if isinstance(payload, AcquisitionFeasibilityRequest):
        return payload
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping or AcquisitionFeasibilityRequest")

    _require_fields(
        payload,
        required=(
            "target_customers",
            "total_budget",
            "daily_budget",
            "cost_per_entry",
            "gross_margin_ltv",
            "stages",
        ),
    )

    raw_stages = payload.get("stages")
    if (
        isinstance(raw_stages, Mapping)
        or isinstance(raw_stages, (str, bytes))
        or not isinstance(raw_stages, Iterable)
    ):
        raise AcquisitionPayloadError(
            "stages must be an iterable of stage mappings or FunnelStage objects"
        )

    stages = tuple(_stage_from_payload(item) for item in raw_stages)
    if not stages:
        raise AcquisitionPayloadError("stages must contain at least one stage")

    return AcquisitionFeasibilityRequest(
        target_customers=coerce_int(payload.get("target_customers"), 0, minimum=0),
        total_budget=coerce_float(payload.get("total_budget"), 0.0, minimum=0.0),
        daily_budget=coerce_float(payload.get("daily_budget"), 0.0, minimum=0.0),
        cost_per_entry=coerce_float(payload.get("cost_per_entry"), 0.0, minimum=0.0),
        gross_margin_ltv=coerce_float(payload.get("gross_margin_ltv"), 0.0, minimum=0.0),
        stages=stages,
        target_days=coerce_float(payload.get("target_days"), 0.0, minimum=0.0),
        setup_cost=coerce_float(payload.get("setup_cost"), 0.0, minimum=0.0),
        max_cac_to_ltv_ratio=coerce_float(
            payload.get("max_cac_to_ltv_ratio"),
            0.33,
            minimum=0.0,
            maximum=1.0,
        ),
        payback_horizon_months=coerce_float(
            payload.get("payback_horizon_months"),
            12.0,
            minimum=0.0,
        ),
        expected_monthly_margin_per_customer=coerce_float(
            payload.get("expected_monthly_margin_per_customer"),
            0.0,
            minimum=0.0,
        ),
    )


def _stage_from_payload(item: Any) -> FunnelStage:
    if isinstance(item, FunnelStage):
        return item
    if not isinstance(item, Mapping):
        raise TypeError("each stage must be a mapping or FunnelStage")

    _require_stage_fields(item, required=("conversion_rate",))
    return FunnelStage(
        name=str(item.get("name") or "stage"),
        conversion_rate=coerce_float(
            item.get("conversion_rate"), 0.0, minimum=0.0, maximum=1.0
        ),
        avg_stage_days=coerce_float(item.get("avg_stage_days"), 0.0, minimum=0.0),
        touchpoints=coerce_int(item.get("touchpoints"), 1, minimum=1),
    )


def _require_fields(payload: Mapping[str, Any], *, required: tuple[str, ...]) -> None:
    missing = tuple(name for name in required if name not in payload)
    if missing:
        raise AcquisitionPayloadError(
            f"missing required payload fields: {', '.join(missing)}"
        )


def _require_stage_fields(
    payload: Mapping[str, Any], *, required: tuple[str, ...]
) -> None:
    missing = tuple(name for name in required if name not in payload)
    if missing:
        raise AcquisitionPayloadError(
            f"missing required stage fields: {', '.join(missing)}"
        )


__all__ = [
    "AcquisitionPayloadError",
    "CANON_ACQUISITION_REQUEST_ADAPTER",
    "request_from_payload",
]
