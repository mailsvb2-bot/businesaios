from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping

CANON_API_ANALYTICS_MODELS = True


def _clone(value: Any) -> Any:
    if is_dataclass(value):
        return _clone(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _clone(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_clone(item) for item in value)
    if isinstance(value, list):
        return tuple(_clone(item) for item in value)
    return value


@dataclass(frozen=True)
class AnalyticsWindowRequest:
    tenant_id: str
    window_days: int = 30


@dataclass(frozen=True)
class AnalyticsSnapshotReadRequest:
    snapshot_id: str


@dataclass(frozen=True)
class AnalyticsSnapshotWriteRequest:
    tenant_id: str
    snapshot_kind: str
    payload: dict[str, Any]
    snapshot_id: str | None = None


@dataclass(frozen=True)
class AnalyticsMaterializeRequest:
    tenant_id: str
    window_days: int = 30
    export_path: str | None = None


@dataclass(frozen=True)
class AnalyticsQueueMaterializeRequest:
    tenant_id: str
    window_days: int = 30
    queue_name: str = 'analytics'
    export_path: str | None = None


@dataclass(frozen=True)
class AnalyticsSignedExportRequest:
    tenant_id: str
    export_id: str
    export_dir: str | None = None
    window_days: int = 30


@dataclass(frozen=True)
class AnalyticsPayloadResponse:
    payload: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {'payload': _clone(self.payload)}
