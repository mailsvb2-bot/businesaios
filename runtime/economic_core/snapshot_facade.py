from __future__ import annotations

from economics.contracts import EconomicSnapshot, TruthFragment


CANON_RUNTIME_ECONOMIC_CORE_SNAPSHOT_FACADE = True


def build_snapshot_from_fragments(*, tenant_id: str, business_id: str, scope_type: str, scope_id: str, fragments: tuple[TruthFragment, ...], spend_total_minor: int = 0) -> EconomicSnapshot:
    booked = 0
    corrected = 0
    refund_total = 0
    reversal_total = 0
    derived_spend_total = int(spend_total_minor or 0)
    derived_cac_minor: int | None = None
    issues: list[str] = []
    ready = True
    for fragment in fragments:
        aggregation_mode = str(getattr(fragment, 'aggregation_mode', 'financial_primary') or 'financial_primary')
        if aggregation_mode == 'financial_primary':
            booked += int(fragment.booked_amount_minor or 0)
            corrected += int(fragment.corrected_amount_minor or 0)
            if fragment.corrected_amount_minor is not None and fragment.booked_amount_minor is not None and fragment.corrected_amount_minor < fragment.booked_amount_minor:
                reversal_total += max(0, int(fragment.booked_amount_minor) - int(fragment.corrected_amount_minor))
        elif aggregation_mode == 'cost_primary':
            derived_spend_total += int(getattr(fragment, 'cost_total_minor', 0) or 0)
            if derived_cac_minor is None and getattr(fragment, 'unit_cost_minor', None) is not None:
                derived_cac_minor = int(getattr(fragment, 'unit_cost_minor'))
        issues.extend(str(item) for item in fragment.issues)
        ready = ready and bool(fragment.ready_for_export)
    if corrected < booked:
        refund_total = booked - corrected
    consistency_status = 'consistent' if not issues else 'inconsistent'
    return EconomicSnapshot(
        tenant_id=tenant_id,
        business_id=business_id,
        scope_type=scope_type,
        scope_id=scope_id,
        revenue_booked_minor=booked,
        revenue_corrected_minor=corrected,
        refund_total_minor=refund_total,
        reversal_total_minor=reversal_total,
        chargeback_total_minor=0,
        spend_total_minor=derived_spend_total,
        margin_minor=corrected - derived_spend_total,
        cac_minor=derived_cac_minor,
        consistency_status=consistency_status,
        issues=tuple(issues),
        ready_for_export=ready and consistency_status == 'consistent',
    )
