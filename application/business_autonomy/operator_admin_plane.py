from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


CANON_UNIFIED_OPERATOR_ADMIN_PLANE = True


@dataclass(frozen=True)
class FleetHealthCard:
    title: str
    value: int | float | str
    status: str
    detail: str


@dataclass(frozen=True)
class FleetView:
    fleet_cards: tuple[FleetHealthCard, ...]
    business_class_rows: tuple[Mapping[str, Any], ...] = ()
    trust_capability_rows: tuple[Mapping[str, Any], ...] = ()
    approval_bottlenecks: tuple[Mapping[str, Any], ...] = ()
    cross_business_failures: tuple[Mapping[str, Any], ...] = ()
    delayed_outcome_quarantine_rows: tuple[Mapping[str, Any], ...] = ()
    distributed_conflict_rows: tuple[Mapping[str, Any], ...] = ()
    export_surface: Mapping[str, Any] = field(default_factory=dict)


# Backward-compatible name for route surfaces; logic remains owned by FleetHealthCard.
FleetCard = FleetHealthCard


class FleetReadModelPort(Protocol):
    def fleet_metrics(self) -> Mapping[str, Any]: ...
    def business_class_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]: ...
    def trust_capability_health(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]: ...
    def approval_bottleneck_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]: ...
    def cross_business_failures(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]: ...
    def export_links(self) -> Mapping[str, Any]: ...


class _EmptyFleetReadModel:
    def fleet_metrics(self) -> Mapping[str, Any]:
        return {
            'businesses_total': 0,
            'healthy_capabilities': 0,
            'pending_approvals': 0,
            'cross_business_failures': 0,
        }

    def business_class_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return ()

    def trust_capability_health(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return ()

    def approval_bottleneck_view(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return ()

    def cross_business_failures(self, *, limit: int = 100) -> Sequence[Mapping[str, Any]]:
        return ()

    def export_links(self) -> Mapping[str, Any]:
        return {'status': 'read_model_unconfigured', 'honest': True}


class UnifiedOperatorAdminPlane:
    def __init__(self, read_model: FleetReadModelPort | None = None) -> None:
        self._read_model = read_model or _EmptyFleetReadModel()

    def get_fleet_view(self, *, limit: int = 100) -> FleetView:
        metrics = dict(self._read_model.fleet_metrics())
        failures = int(metrics.get("cross_business_failures") or 0)
        delayed_health = _call_optional_mapping(self._read_model, 'delayed_outcome_health')
        delayed_rows = tuple(_call_optional_sequence(self._read_model, 'delayed_outcome_quarantine_view', limit=limit))
        conflict_rows = tuple(_call_optional_sequence(self._read_model, 'distributed_conflict_view', limit=limit))
        if not conflict_rows:
            conflict_rows = tuple(_read_distributed_conflicts_from_data_dir(limit=limit))
        delayed_quarantined = int(delayed_health.get('quarantined_total') or delayed_health.get('quarantined') or len(delayed_rows) or 0)
        distributed_conflicts = int(metrics.get('distributed_conflicts') or len(conflict_rows) or 0)
        cards = [
            FleetHealthCard("businesses_total", int(metrics.get("businesses_total") or 0), "ok", "registered businesses"),
            FleetHealthCard("healthy_capabilities", int(metrics.get("healthy_capabilities") or 0), "ok", "capabilities healthy"),
            FleetHealthCard("pending_approvals", int(metrics.get("pending_approvals") or 0), "warning", "human bottlenecks"),
            FleetHealthCard("cross_business_failures", failures, "error" if failures else "ok", "shared incidents"),
            FleetHealthCard("Delayed Outcomes", delayed_quarantined, "warning" if delayed_quarantined else "ok", "delayed outcome quarantine"),
            FleetHealthCard("Distributed Conflicts", distributed_conflicts, "warning" if distributed_conflicts else "ok", "distributed state conflicts"),
        ]
        return FleetView(
            fleet_cards=tuple(cards),
            business_class_rows=tuple(self._read_model.business_class_view(limit=limit)),
            trust_capability_rows=tuple(self._read_model.trust_capability_health(limit=limit)),
            approval_bottlenecks=tuple(self._read_model.approval_bottleneck_view(limit=limit)),
            cross_business_failures=tuple(self._read_model.cross_business_failures(limit=limit)),
            delayed_outcome_quarantine_rows=delayed_rows or tuple(metrics.get("delayed_outcome_quarantine_rows") or ()),
            distributed_conflict_rows=conflict_rows,
            export_surface=dict(self._read_model.export_links()),
        )


def _call_optional_mapping(target: object, method_name: str) -> Mapping[str, Any]:
    method = getattr(target, method_name, None)
    if method is None:
        return {}
    value = method()
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _call_optional_sequence(target: object, method_name: str, *, limit: int) -> Sequence[Mapping[str, Any]]:
    method = getattr(target, method_name, None)
    if method is None:
        return ()
    try:
        value = method(limit=limit)
    except TypeError:
        value = method()
    return tuple(item for item in (value or ()) if isinstance(item, Mapping))


def _read_distributed_conflicts_from_data_dir(*, limit: int) -> Sequence[Mapping[str, Any]]:
    import json
    import os
    from pathlib import Path

    root = Path(os.environ.get('DATA_DIR') or os.environ.get('BUSINESAIOS_DATA_DIR') or 'data')
    path = root / 'runtime' / 'distributed' / 'append' / 'distributed_state_conflicts_state.json'
    if not path.exists():
        return ()
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return ()
    items = payload.get('items') if isinstance(payload, dict) else None
    if not isinstance(items, dict):
        return ()
    return tuple(dict(item) for item in list(items.values())[:limit] if isinstance(item, Mapping))


__all__ = [
    "CANON_UNIFIED_OPERATOR_ADMIN_PLANE",
    "FleetCard",
    "FleetHealthCard",
    "FleetReadModelPort",
    "FleetView",
    "UnifiedOperatorAdminPlane",
]
