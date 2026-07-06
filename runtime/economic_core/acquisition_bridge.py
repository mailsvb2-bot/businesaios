from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from economics.contracts import TruthFragment

CANON_RUNTIME_ECONOMIC_CORE_ACQUISITION_BRIDGE = True


def build_acquisition_truth_snapshot_from_client_outcome(*, truth_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    truth = dict(truth_snapshot)
    acquisition_cost = truth.get("acquisition_cost")
    cac = truth.get("cac")
    try:
        cost_total_minor = int(round(float(acquisition_cost or 0.0) * 100))
    except (TypeError, ValueError):
        cost_total_minor = 0
    try:
        unit_cost_minor = int(round(float(cac or 0.0) * 100))
    except (TypeError, ValueError):
        unit_cost_minor = None
    return {
        "tenant_id": str(truth.get("tenant_id") or ""),
        "business_id": str(truth.get("business_id") or ""),
        "entity_id": str(truth.get("order_id") or ""),
        "acquisition_status": "attributed" if cost_total_minor > 0 else "unknown",
        "cost_total_minor": cost_total_minor,
        "unit_cost_minor": unit_cost_minor,
        "source_channel": str(truth.get("source_channel") or ""),
        "ready_for_export": bool(truth.get("reconciliation_consistent")),
        "issues": tuple(),
    }


def build_acquisition_truth_fragment(*, acquisition_snapshot: Mapping[str, Any]) -> TruthFragment:
    snapshot = dict(acquisition_snapshot)
    source_channel = str(snapshot.get("source_channel") or "").strip()
    evidence_refs = (source_channel,) if source_channel else ()
    return TruthFragment(
        tenant_id=str(snapshot.get("tenant_id") or ""),
        business_id=str(snapshot.get("business_id") or ""),
        domain="acquisition",
        entity_id=str(snapshot.get("entity_id") or ""),
        commercial_status=str(snapshot.get("acquisition_status") or "unknown"),
        lifecycle_stages=("acquisition_cost_attributed",) if int(snapshot.get("cost_total_minor") or 0) > 0 else tuple(),
        booked_amount_minor=None,
        corrected_amount_minor=None,
        currency=None,
        cost_total_minor=int(snapshot.get("cost_total_minor") or 0),
        unit_cost_minor=None if snapshot.get("unit_cost_minor") is None else int(snapshot.get("unit_cost_minor")),
        aggregation_mode="cost_primary" if int(snapshot.get("cost_total_minor") or 0) > 0 else "consistency_only",
        issues=tuple(str(item) for item in tuple(snapshot.get("issues") or ())),
        evidence_refs=evidence_refs,
        ready_for_export=bool(snapshot.get("ready_for_export")),
    )
