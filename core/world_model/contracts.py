from __future__ import annotations

from typing import Any, Protocol

from core.world_model.types import (
    ReadResult,
    SnapshotRejection,
    WorldModelBuildInput,
    WorldSnapshot,
    WorldSnapshotRequest,
)

WORLD_SNAPSHOT_SCHEMA_VERSION = "world_snapshot@v1"
WORLD_SNAPSHOT_ROLE = "state_snapshot_only"
WORLD_SNAPSHOT_DECISION_ISSUER = "none"
WORLD_SNAPSHOT_READ_ONLY = True

FORBIDDEN_DECISION_KEYS = (
    "action",
    "actions",
    "decision",
    "decide",
    "executor",
    "execute",
    "route",
    "issuer_id",
    "deployment_proposal",
    "manual_override",
    "selected_strategy",
    "selected_action",
    "autopilot_apply",
    "campaign_apply",
)


class WorldSnapshotBuilderPort(Protocol):
    def build(self, request: WorldSnapshotRequest) -> WorldSnapshot:
        ...


class CustomerReader(Protocol):
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        ...


class RevenueReader(Protocol):
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        ...


class CampaignReader(Protocol):
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        ...


class ProductReader(Protocol):
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        ...


class MessagingReader(Protocol):
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        ...


class MarketReader(Protocol):
    def read(self, *, build_input: WorldModelBuildInput) -> ReadResult[dict]:
        ...


class SnapshotRepository(Protocol):
    def put_snapshot(self, snapshot: WorldSnapshot) -> None:
        ...

    def put_rejection(self, rejection: SnapshotRejection) -> None:
        ...

    def get_latest(self, *, tenant_id: str, business_id: str) -> WorldSnapshot | None:
        ...

    def get_history(self, *, tenant_id: str, business_id: str) -> list[WorldSnapshot]:
        ...


class WorldSnapshotSerializer(Protocol):
    def to_dict(self, snapshot: WorldSnapshot) -> dict[str, Any]:
        ...

    def to_canonical_json(self, snapshot: WorldSnapshot) -> str:
        ...


class SnapshotEventPublisher(Protocol):
    def publish_snapshot_built(self, snapshot: WorldSnapshot) -> None:
        ...

    def publish_snapshot_rejected(self, rejection: SnapshotRejection) -> None:
        ...
