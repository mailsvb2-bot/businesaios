from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


CANON_REGION_OWNERSHIP_PLANE = True


@dataclass(frozen=True)
class RegionRoute:
    tenant_id: str
    business_id: str
    primary_region: str
    failover_region: str
    routing_epoch: int
    ownership_token: int


@dataclass(frozen=True)
class FailoverDecision:
    accepted: bool
    reason: str
    previous_region: str
    target_region: str
    new_routing_epoch: int
    cutover_barrier_id: str


class StaleReaderError(ValueError):
    pass


class RegionStatePort(Protocol):
    def read_route(self, *, tenant_id: str, business_id: str) -> RegionRoute | None: ...
    def compare_and_swap_route(self, *, tenant_id: str, business_id: str, expected_epoch: int | None, route: RegionRoute) -> bool: ...
    def allocate_cutover_barrier(self, *, tenant_id: str, business_id: str, target_region: str) -> str: ...


class StaleReaderGuard:
    def validate(self, *, observed_epoch: int, current_epoch: int) -> None:
        if int(observed_epoch) < int(current_epoch):
            raise StaleReaderError("stale-reader protection triggered")


class RegionOwnershipPlane:
    def __init__(self, *, state: RegionStatePort, stale_reader_guard: StaleReaderGuard | None = None) -> None:
        self._state = state
        self._stale_reader_guard = stale_reader_guard or StaleReaderGuard()

    def read_current_route(self, *, tenant_id: str, business_id: str, observed_epoch: int | None = None) -> RegionRoute:
        route = self._state.read_route(tenant_id=tenant_id, business_id=business_id)
        if route is None:
            raise KeyError(f"region route missing: {tenant_id}:{business_id}")
        if observed_epoch is not None:
            self._stale_reader_guard.validate(observed_epoch=int(observed_epoch), current_epoch=route.routing_epoch)
        return route

    def failover(self, *, tenant_id: str, business_id: str, expected_epoch: int, reason: str) -> FailoverDecision:
        current = self.read_current_route(tenant_id=tenant_id, business_id=business_id, observed_epoch=expected_epoch)
        barrier_id = self._state.allocate_cutover_barrier(tenant_id=tenant_id, business_id=business_id, target_region=current.failover_region)
        next_route = RegionRoute(
            tenant_id=current.tenant_id,
            business_id=current.business_id,
            primary_region=current.failover_region,
            failover_region=current.primary_region,
            routing_epoch=int(current.routing_epoch) + 1,
            ownership_token=int(current.ownership_token) + 1,
        )
        accepted = self._state.compare_and_swap_route(
            tenant_id=tenant_id,
            business_id=business_id,
            expected_epoch=current.routing_epoch,
            route=next_route,
        )
        return FailoverDecision(
            accepted=bool(accepted),
            reason=str(reason),
            previous_region=current.primary_region,
            target_region=next_route.primary_region if accepted else current.primary_region,
            new_routing_epoch=next_route.routing_epoch if accepted else current.routing_epoch,
            cutover_barrier_id=barrier_id,
        )


__all__ = [
    "CANON_REGION_OWNERSHIP_PLANE",
    "FailoverDecision",
    "RegionOwnershipPlane",
    "RegionRoute",
    "RegionStatePort",
    "StaleReaderError",
    "StaleReaderGuard",
]
