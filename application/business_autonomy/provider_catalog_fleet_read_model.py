from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from collections.abc import Mapping, Sequence

from application.business_autonomy.delayed_outcome_bridge import BusinessAutonomyDelayedOutcomeBridge
from application.business_autonomy.provider_catalog import provider_map


def _safe_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _distributed_conflicts_state_path() -> Path:
    return Path(os.getenv("DATA_DIR", ".")) / "runtime" / "distributed" / "append" / "distributed_state_conflicts_state.json"


def _read_conflict_rows(limit: int) -> tuple[dict[str, Any], ...]:
    path = _distributed_conflicts_state_path()
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    items = _safe_mapping(payload.get("items"))
    rows = [dict(item) for item in items.values()]
    rows.sort(key=lambda row: (str(row.get("resolved_at_utc") or row.get("acknowledged_at_utc") or ""), str(row.get("document") or ""), str(row.get("business_id") or "")), reverse=True)
    return tuple(rows[: max(0, int(limit))])


@dataclass(frozen=True)
class ProviderCatalogFleetReadModel:
    def fleet_metrics(self) -> Mapping[str, Any]:
        providers = tuple(provider_map().values())
        conflicts = _read_conflict_rows(limit=1000)
        open_conflicts = sum(1 for row in conflicts if str(row.get("status") or "open") != "resolved")
        return {
            'businesses_total': 0,
            'healthy_capabilities': len({str(getattr(item, 'channel_kind', '') or '').strip() for item in providers if str(getattr(item, 'channel_kind', '') or '').strip()}),
            'pending_approvals': 0,
            'open_conflicts': open_conflicts,
        }

    def business_class_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for provider in tuple(provider_map().values()):
            channel_kind = str(getattr(provider, 'channel_kind', '') or '').strip()
            if not channel_kind or channel_kind in seen:
                continue
            seen.add(channel_kind)
            rows.append({'business_id': '', 'channel_kind': channel_kind, 'region': 'not_configured', 'persistent_surfaces': list(tuple(getattr(provider, 'persistent_surfaces', ()) or ())), 'status': 'not_configured', 'source': 'provider_catalog'})
            if len(rows) >= max(0, int(limit)):
                break
        return tuple(rows)

    def trust_capability_health(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return ()

    def approval_bottleneck_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return ()

    def cross_business_failures(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return ()

    def export_links(self) -> Mapping[str, Any]:
        return {'bundle': '', 'status': 'not_configured'}

    def delayed_outcome_health(self) -> Mapping[str, Any]:
        bridge = BusinessAutonomyDelayedOutcomeBridge.default()
        summary = dict(bridge.quarantine_summary())
        return {'active_total': len(bridge.list_active()), 'quarantined_total': int(summary.get('quarantined_total', 0)), 'by_reason': dict(summary.get('by_reason') or {})}

    def delayed_outcome_quarantine_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        bridge = BusinessAutonomyDelayedOutcomeBridge.default()
        return tuple({'outcome_id': item.outcome_id, 'tenant_id': item.tenant_id, 'business_id': item.business_id, 'goal_id': item.goal_id, 'reason': item.quarantine_reason, 'quarantined_at_utc': item.quarantined_at_utc} for item in bridge.list_quarantined()[: max(0, int(limit))])

    def delayed_outcome_sweep_runs(self, *, limit: int = 20) -> Sequence[Mapping[str, Any]]:
        bridge = BusinessAutonomyDelayedOutcomeBridge.default()
        return tuple({'run_id': item.run_id, 'operation': item.operation, 'status': item.status, 'linked_outcome_ids': list(item.linked_outcome_ids), 'completed_at_utc': item.completed_at_utc} for item in bridge.list_sweep_runs(limit=limit))

    def delayed_outcome_action_rows(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        bridge = BusinessAutonomyDelayedOutcomeBridge.default()
        return tuple({'action_id': item.action_id, 'action_type': item.action_type, 'outcome_id': item.outcome_id, 'actor': item.actor, 'reason': item.reason, 'run_id': item.run_id, 'created_at_utc': item.created_at_utc} for item in bridge.list_action_ledger(limit=limit))

    def distributed_state_conflict_rows(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return _read_conflict_rows(limit=limit)


__all__ = ['ProviderCatalogFleetReadModel']
