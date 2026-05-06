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


class UnifiedOperatorAdminPlane:
    def __init__(self, read_model: FleetReadModelPort) -> None:
        self._read_model = read_model

    def get_fleet_view(self, *, limit: int = 100) -> FleetView:
        metrics = dict(self._read_model.fleet_metrics())
        failures = int(metrics.get("cross_business_failures") or 0)
        cards = (
            FleetHealthCard("businesses_total", int(metrics.get("businesses_total") or 0), "ok", "registered businesses"),
            FleetHealthCard("healthy_capabilities", int(metrics.get("healthy_capabilities") or 0), "ok", "capabilities healthy"),
            FleetHealthCard("pending_approvals", int(metrics.get("pending_approvals") or 0), "warning", "human bottlenecks"),
            FleetHealthCard("cross_business_failures", failures, "error" if failures else "ok", "shared incidents"),
        )
        return FleetView(
            fleet_cards=cards,
            business_class_rows=tuple(self._read_model.business_class_view(limit=limit)),
            trust_capability_rows=tuple(self._read_model.trust_capability_health(limit=limit)),
            approval_bottlenecks=tuple(self._read_model.approval_bottleneck_view(limit=limit)),
            cross_business_failures=tuple(self._read_model.cross_business_failures(limit=limit)),
            delayed_outcome_quarantine_rows=tuple(metrics.get("delayed_outcome_quarantine_rows") or ()),
            export_surface=dict(self._read_model.export_links()),
        )


__all__ = [
    "CANON_UNIFIED_OPERATOR_ADMIN_PLANE",
    "FleetCard",
    "FleetHealthCard",
    "FleetReadModelPort",
    "FleetView",
    "UnifiedOperatorAdminPlane",
]
