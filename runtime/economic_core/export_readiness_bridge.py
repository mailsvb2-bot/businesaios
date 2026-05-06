from __future__ import annotations

from typing import Any, Mapping

from economics.contracts import TruthFragment

CANON_RUNTIME_ECONOMIC_CORE_EXPORT_READINESS_BRIDGE = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def build_export_readiness_snapshot(*, reconciliation: Mapping[str, Any] | None, anomaly_snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    recon = _safe_dict(reconciliation)
    anomaly = _safe_dict(anomaly_snapshot)
    blockers: list[str] = []
    if not bool(recon.get('consistent', False)):
        blockers.append('reconciliation_not_consistent')
    if bool(anomaly.get('has_issues')):
        blockers.append('anomalies_present')
    blockers_tuple = tuple(dict.fromkeys(item for item in blockers if item))
    return {
        'tenant_id': str(recon.get('tenant_id') or anomaly.get('tenant_id') or ''),
        'business_id': str(recon.get('business_id') or anomaly.get('business_id') or ''),
        'entity_id': str(recon.get('order_id') or anomaly.get('entity_id') or ''),
        'export_status': 'ready' if not blockers_tuple else 'blocked',
        'ready': not blockers_tuple,
        'blockers': blockers_tuple,
        'ready_for_export': not blockers_tuple,
    }


def build_export_readiness_fragment(*, export_readiness_snapshot: Mapping[str, Any]) -> TruthFragment:
    snapshot = dict(export_readiness_snapshot)
    return TruthFragment(
        tenant_id=str(snapshot.get('tenant_id') or ''),
        business_id=str(snapshot.get('business_id') or ''),
        domain='export_readiness',
        entity_id=str(snapshot.get('entity_id') or ''),
        commercial_status=str(snapshot.get('export_status') or 'blocked'),
        lifecycle_stages=('export_ready',) if bool(snapshot.get('ready')) else ('export_blocked',),
        booked_amount_minor=None,
        corrected_amount_minor=None,
        currency=None,
        aggregation_mode='consistency_only',
        issues=tuple(str(item) for item in tuple(snapshot.get('blockers') or ())),
        ready_for_export=bool(snapshot.get('ready_for_export')),
    )
