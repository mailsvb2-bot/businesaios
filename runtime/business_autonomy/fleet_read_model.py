from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from application.business_autonomy.distributed_capability_trust_registry import DistributedBusinessRegistry
from application.business_autonomy.operator_admin_plane import FleetReadModelPort
from governance.approval_store import build_default_approval_store


@dataclass
class BusinessAutonomyFleetReadModel(FleetReadModelPort):
    registry: DistributedBusinessRegistry

    def fleet_metrics(self) -> Mapping[str, Any]:
        rows = self.registry.list_for_tenant(tenant_id='tenant-demo', limit=500)
        pending = 0
        try:
            store = build_default_approval_store()
            pending = len([item for item in store.list_recent(limit=500) if item.status.value == 'requested'])
        except Exception:
            pending = 0
        return {
            'businesses_total': len(rows),
            'healthy_capabilities': sum(1 for row in rows if row.capabilities),
            'pending_approvals': pending,
            'cross_business_failures': 0,
        }

    def business_class_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        rows = self.registry.list_for_tenant(tenant_id='tenant-demo', limit=limit)
        return [
            {
                'business_id': row.business_id,
                'channel_kind': row.channel_kind,
                'region': row.region,
                'persistent_surfaces': list(row.persistent_surfaces),
            }
            for row in rows
        ]

    def trust_capability_health(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        rows = self.registry.list_for_tenant(tenant_id='tenant-demo', limit=limit)
        return [
            {
                'business_id': row.business_id,
                'trust_tier': row.trust.trust_tier.value,
                'capability_count': len(row.capabilities),
                'governance_enabled': row.governance_enabled,
            }
            for row in rows
        ]

    def approval_bottleneck_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        try:
            store = build_default_approval_store()
            return [
                {
                    'approval_id': item.approval_id,
                    'tenant_id': item.tenant_id,
                    'status': item.status.value,
                }
                for item in store.list_recent(limit=limit)
                if item.status.value == 'requested'
            ]
        except Exception:
            return []

    def cross_business_failures(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return []

    def export_links(self) -> Mapping[str, Any]:
        return {'fleet_export': 'business_autonomy_fleet_export'}
