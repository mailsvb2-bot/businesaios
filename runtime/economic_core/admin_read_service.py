from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Iterable

from economics.contracts import TruthFragment
from runtime.economic_core.assembler import assemble_truth_fragments
from runtime.economic_core.snapshot_facade import build_snapshot_from_fragments

CANON_RUNTIME_ECONOMIC_CORE_ADMIN_READ_SERVICE = True


@dataclass(frozen=True, slots=True)
class EconomicAdminReadService:
    def build_read_model(
        self,
        *,
        scope_type: str,
        scope_id: str,
        tenant_id: str,
        business_id: str,
        truth_payload: dict[str, Any],
        truth_fragment: object | None = None,
        fragments: Iterable[TruthFragment | None] = (),
        extra_widgets: Iterable[dict[str, Any]] = (),
        spend_total_minor: int = 0,
    ) -> dict[str, Any]:
        assembled_fragments = assemble_truth_fragments(
            truth_fragment if hasattr(truth_fragment, 'domain') else None,
            *tuple(fragment for fragment in fragments if hasattr(fragment, 'domain')),
        )
        snapshot = build_snapshot_from_fragments(
            tenant_id=tenant_id,
            business_id=business_id,
            scope_type=scope_type,
            scope_id=scope_id,
            fragments=assembled_fragments,
            spend_total_minor=spend_total_minor,
        )
        snapshot_payload = {
            'tenant_id': snapshot.tenant_id,
            'business_id': snapshot.business_id,
            'scope_type': snapshot.scope_type,
            'scope_id': snapshot.scope_id,
            'revenue_booked_minor': snapshot.revenue_booked_minor,
            'revenue_corrected_minor': snapshot.revenue_corrected_minor,
            'refund_total_minor': snapshot.refund_total_minor,
            'reversal_total_minor': snapshot.reversal_total_minor,
            'chargeback_total_minor': snapshot.chargeback_total_minor,
            'spend_total_minor': snapshot.spend_total_minor,
            'margin_minor': snapshot.margin_minor,
            'cac_minor': snapshot.cac_minor,
            'consistency_status': snapshot.consistency_status,
            'issues': snapshot.issues,
            'ready_for_export': snapshot.ready_for_export,
            'domains': tuple(fragment.domain for fragment in assembled_fragments),
        }
        widgets = [
            {
                'widget_id': 'economic_truth_widget',
                'kind': 'economic_truth',
                'payload': truth_payload,
            },
            {
                'widget_id': 'economic_snapshot_widget',
                'kind': 'economic_snapshot',
                'payload': snapshot_payload,
            },
            {
                'widget_id': 'economic_fragments_widget',
                'kind': 'economic_fragments',
                'payload': {
                    'fragments': tuple(
                        {
                            'domain': fragment.domain,
                            'aggregation_mode': str(getattr(fragment, 'aggregation_mode', 'financial_primary') or 'financial_primary'),
                            'commercial_status': fragment.commercial_status,
                            'entity_id': fragment.entity_id,
                            'cost_total_minor': getattr(fragment, 'cost_total_minor', None),
                            'unit_cost_minor': getattr(fragment, 'unit_cost_minor', None),
                        }
                        for fragment in assembled_fragments
                    ),
                },
            },
        ]
        widgets.extend(dict(item) for item in extra_widgets)
        return {
            'scope_type': scope_type,
            'scope_id': scope_id,
            'tenant_id': tenant_id,
            'business_id': business_id,
            'truth': truth_payload,
            'snapshot': snapshot_payload,
            'widgets': tuple(widgets),
        }
