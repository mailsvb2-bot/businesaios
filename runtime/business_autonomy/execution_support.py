from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from time import time
from typing import Any

from core.events.event_types import DECISION_PROPOSED
from core.utils.canonical import payload_hash as canonical_payload_hash
from governance.persistence_codec import to_jsonable
from runtime.business_autonomy.distributed_state import FileRegionRouteState
from runtime.execution.distributed_execution_plane import (
    DistributedExecutionPlanner,
    GlobalGovernorVerdict,
    HashRingShardMap,
    QueueSlice,
)
from runtime.execution.region_ownership_plane import RegionOwnershipPlane, RegionRoute


CANON_EXTERNAL_DECISION_PROVENANCE = True
_DECISION_EVENT_SOURCE = "application.decision_runtime"


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class DecisionEventSpineProvenanceVerifier:
    """Bind managed external execution to the canonical signed-decision lineage.

    This verifier intentionally performs no cryptography. Decision signatures stay
    owned by DecisionCore/RuntimeGuard. Here we only require the durable
    decision.proposed projection that the canonical decision runtime emitted from
    the signed DecisionEnvelope and bind it exactly to ActionIntentV2.
    """

    event_store: object

    def assert_intent_provenance(self, intent: object) -> str:
        iter_events = getattr(self.event_store, "iter_events", None)
        if not callable(iter_events):
            raise RuntimeError("canonical decision event store is unavailable")

        tenant_id = _text(getattr(intent, "tenant_id", ""))
        decision_id = _text(getattr(intent, "decision_id", ""))
        matches = [
            dict(raw)
            for raw in iter_events(
                tenant_id=tenant_id,
                start_ms=0,
                event_type=DECISION_PROPOSED,
            )
            if _text(_mapping(raw).get("decision_id")) == decision_id
        ]
        if not matches:
            raise LookupError("canonical decision provenance not found")
        if len(matches) != 1:
            raise ValueError("canonical decision provenance is ambiguous")

        event = matches[0]
        if _text(event.get("source")) != _DECISION_EVENT_SOURCE:
            raise ValueError("canonical decision provenance source mismatch")
        payload = _mapping(event.get("payload"))
        decision = _mapping(payload.get("decision"))

        as_dict = getattr(intent, "as_dict", None)
        if not callable(as_dict):
            raise ValueError("canonical ActionIntent projection is required")
        expected = {
            "tenant_id": tenant_id,
            "business_id": _text(getattr(intent, "business_id", "")),
            "decision_id": decision_id,
            "correlation_id": _text(getattr(intent, "correlation_id", "")),
            "goal_id": _text(getattr(intent, "goal_id", "")),
            "agent_id": _text(getattr(intent, "agent_id", "")),
            "action_type": _text(getattr(intent, "capability_target", "")),
            "action_intent_id": _text(getattr(intent, "intent_id", "")),
            "action_intent_fingerprint": canonical_payload_hash(to_jsonable(as_dict())),
            "decision_payload_hash": _text(getattr(intent, "payload_hash", "")),
        }
        actual = {
            "tenant_id": _text(event.get("tenant_id")),
            "business_id": _text(payload.get("business_id")),
            "decision_id": _text(event.get("decision_id")),
            "correlation_id": _text(event.get("correlation_id")),
            "goal_id": _text(decision.get("goal_id")),
            "agent_id": _text(payload.get("agent_id")),
            "action_type": _text(decision.get("action_type")),
            "action_intent_id": _text(decision.get("action_intent_id")),
            "action_intent_fingerprint": _text(decision.get("action_intent_fingerprint")),
            "decision_payload_hash": _text(decision.get("decision_payload_hash")),
        }
        mismatches = sorted(key for key, value in expected.items() if actual.get(key) != value)
        if mismatches:
            raise ValueError(
                "canonical decision provenance mismatch: " + ",".join(mismatches)
            )
        issued_at_ms = int(decision.get("issued_at_ms") or 0)
        expires_at_ms = int(decision.get("expires_at_ms") or 0)
        if issued_at_ms <= 0 or expires_at_ms <= issued_at_ms:
            raise ValueError("canonical decision provenance lifetime is invalid")
        if int(time() * 1000) >= expires_at_ms:
            raise ValueError("canonical decision provenance is expired")
        event_id = _text(event.get("event_id"))
        if not event_id:
            raise ValueError("canonical decision provenance event_id is required")
        return event_id


@dataclass(frozen=True)
class StaticReplayRecovery:
    def classify(self, *, queue_name: str, tenant_id: str, shard_id: int) -> str:
        if "critical" in str(queue_name):
            return "replay_then_resume"
        return "resume_only"


@dataclass(frozen=True)
class FleetPressureGovernor:
    base_limit: int = 32
    hot_partition_penalty: int = 8
    global_depth_limit: int = 10000

    def evaluate(self, *, queue_name: str, slices: Sequence[QueueSlice], desired_claims: int) -> GlobalGovernorVerdict:
        total_depth = sum(max(0, int(item.depth)) for item in slices)
        hot = any(bool(item.hot_partition) for item in slices)
        if total_depth >= self.global_depth_limit:
            return GlobalGovernorVerdict(False, 0, 5, "global_backpressure")
        allocated = max(1, min(int(desired_claims), self.base_limit - (self.hot_partition_penalty if hot else 0)))
        delay = 2 if hot else 0
        return GlobalGovernorVerdict(True, allocated, delay, "hot_partition" if hot else "steady")


@dataclass(frozen=True)
class BusinessAutonomyExecutionRuntime:
    planner: DistributedExecutionPlanner
    region_plane: RegionOwnershipPlane


def build_execution_runtime(*, route_state: FileRegionRouteState) -> BusinessAutonomyExecutionRuntime:
    planner = DistributedExecutionPlanner(
        shard_map=HashRingShardMap(regions=("eu-west-1", "us-east-1"), shards_per_region=64, owner_prefix="business-autonomy"),
        governor=FleetPressureGovernor(),
        replay_recovery=StaticReplayRecovery(),
    )
    region_plane = RegionOwnershipPlane(state=route_state)
    return BusinessAutonomyExecutionRuntime(planner=planner, region_plane=region_plane)


def ensure_business_route(*, route_state: FileRegionRouteState, tenant_id: str, business_id: str, primary_region: str, failover_region: str) -> RegionRoute:
    existing = route_state.read_route(tenant_id=tenant_id, business_id=business_id)
    if existing is not None:
        return existing
    route = RegionRoute(
        tenant_id=tenant_id,
        business_id=business_id,
        primary_region=primary_region,
        failover_region=failover_region,
        routing_epoch=0,
        ownership_token=1,
    )
    route_state.compare_and_swap_route(tenant_id=tenant_id, business_id=business_id, expected_epoch=None, route=route)
    return route_state.read_route(tenant_id=tenant_id, business_id=business_id) or route


def build_provider_quota_runtime():
    from connectors.platform.connector_quota_guard import ConnectorQuotaGuard
    from runtime.platform.tenancy.tenant_registry import build_default_tenant_quota_counter_store
    from tenancy.tenant_policy_store import build_default_tenant_policy_store
    from tenancy.tenant_quota_guard import TenantQuotaGuard

    counter_store = build_default_tenant_quota_counter_store()
    policy_store = build_default_tenant_policy_store()
    guard = ConnectorQuotaGuard(
        quota_guard=TenantQuotaGuard(
            policy_store=policy_store,
            counter_store=counter_store,
        ),
        counter_store=counter_store,
    )
    return guard, policy_store


def ensure_provider_quota_tenant(policy_store, tenant_id: str) -> None:
    from tenancy.tenant_policy_store import ensure_tenant_policy_bundle

    ensure_tenant_policy_bundle(policy_store, tenant_id)


__all__ = [
    "BusinessAutonomyExecutionRuntime",
    "FleetPressureGovernor",
    "StaticReplayRecovery",
    "DecisionEventSpineProvenanceVerifier",
    "build_execution_runtime",
    "build_provider_quota_runtime",
    "ensure_provider_quota_tenant",
    "ensure_business_route",
]
