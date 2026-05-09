from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, is_dataclass
import gzip
import json
from pathlib import Path
from typing import Any, Protocol, TypeVar

from runtime.platform.support.contracts.action import Action
from runtime.platform.support.contracts.observation import Observation
from runtime.platform.support.contracts.reward import Reward
from runtime.platform.support.contracts.trajectory import Trajectory
from runtime.platform.support.contracts.transition import Transition

def compress(data: bytes) -> bytes:
    return gzip.compress(data)

def decompress(data: bytes) -> bytes:
    return gzip.decompress(data)

class TrajectoryReader(Protocol):
    def read(self) -> Iterable[Trajectory]:
        ...

class DataCatalog:
    def __init__(self) -> None:
        self._datasets: dict[str, str] = {}
    def register(self, name: str, uri: str) -> None:
        self._datasets[name] = uri
    def resolve(self, name: str) -> str:
        return self._datasets[name]

@dataclass(frozen=True)
class DatasetIdentity:
    dataset_id: str

class DatasetLineage:
    def __init__(self) -> None:
        self._lineage: dict[str, str] = {}
    def record(self, child: str, parent: str) -> None:
        self._lineage[child] = parent

class DatasetLoader:
    def load(self, uri: str) -> Iterable[Trajectory]:
        path = Path(uri)
        if not path.exists():
            raise FileNotFoundError(path)
        if path.is_dir():
            raise IsADirectoryError(path)
        trajectories: list[Trajectory] = []
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            trajectories.append(_trajectory_from_payload(payload, line_number=line_number, source=path))
        return tuple(trajectories)

def _trajectory_from_payload(payload: object, *, line_number: int, source: Path) -> Trajectory:
    if not isinstance(payload, dict):
        raise ValueError(f"{source}:{line_number}: trajectory row must be an object")
    transitions_payload = payload.get("transitions")
    if not isinstance(transitions_payload, list):
        raise ValueError(f"{source}:{line_number}: trajectory.transitions must be a list")
    transitions = tuple(_transition_from_payload(item, line_number=line_number, source=source) for item in transitions_payload)
    return Trajectory(transitions=transitions)

def _transition_from_payload(payload: object, *, line_number: int, source: Path) -> Transition:
    if not isinstance(payload, dict):
        raise ValueError(f"{source}:{line_number}: transition must be an object")
    observation_payload = payload.get("observation")
    action_payload = payload.get("action")
    reward_payload = payload.get("reward")
    done = bool(payload.get("done", False))
    if not isinstance(observation_payload, dict):
        raise ValueError(f"{source}:{line_number}: transition.observation must be an object")
    if not isinstance(action_payload, dict):
        raise ValueError(f"{source}:{line_number}: transition.action must be an object")
    if not isinstance(reward_payload, dict):
        raise ValueError(f"{source}:{line_number}: transition.reward must be an object")
    return Transition(
        observation=Observation(data=_observation_data(observation_payload)),
        action=Action(name=str(action_payload.get("name", "")), payload=_action_payload(action_payload)),
        reward=Reward(value=float(reward_payload.get("value", 0.0))),
        done=done,
    )


def _observation_data(payload: dict[str, Any]) -> dict[str, Any]:
    raw_values = payload.get("values") if isinstance(payload.get("values"), dict) else payload.get("data")
    if isinstance(raw_values, dict):
        return {str(key): value for key, value in raw_values.items()}
    return {str(key): value for key, value in payload.items()}


def _action_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("params") if isinstance(payload.get("params"), dict) else payload.get("payload")
    return {str(k): v for k, v in dict(raw or {}).items()}

class DatasetRegistry:
    def __init__(self) -> None:
        self._items: dict[str, str] = {}
    def register(self, dataset_id: str, uri: str) -> None:
        self._items[dataset_id] = uri
    def get(self, dataset_id: str) -> str:
        return self._items[dataset_id]

class DatasetVersioning:
    def __init__(self) -> None:
        self._versions: dict[str, int] = {}
    def next(self, dataset: str) -> int:
        self._versions[dataset] = self._versions.get(dataset, 0) + 1
        return self._versions[dataset]

class DatasetWriter:
    def write(self, uri: str, items: Iterable[Trajectory]) -> None:
        path = Path(uri)
        if path.exists() and path.is_dir():
            raise IsADirectoryError(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [json.dumps(_normalize(item), ensure_ascii=False, sort_keys=True) for item in items]
        text = ("\n".join(rows) + ("\n" if rows else ""))
        path.write_text(text, encoding="utf-8")

def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _normalize(val) for key, val in asdict(value).items()}
    if isinstance(value, tuple):
        return [_normalize(item) for item in value]
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize(val) for key, val in value.items()}
    return value

def simple_drift(old: float, new: float, threshold: float = 0.1) -> bool:
    return abs(old - new) > threshold

def not_none(value: Any) -> bool:
    return value is not None

T = TypeVar("T")
def partition(items: Iterable[T], *, parts: int) -> tuple[tuple[T, ...], ...]:
    buckets = [[] for _ in range(max(1, parts))]
    for index, item in enumerate(items):
        buckets[index % len(buckets)].append(item)
    return tuple(tuple(bucket) for bucket in buckets)

def trajectory_not_empty(t: Trajectory) -> bool:
    return bool(t.transitions)

class RetentionPolicy:
    def __init__(self, days: int) -> None:
        self.days = days

DEFAULT_RETENTION_DAYS = 30

def shard_index(key: str, shard_count: int) -> int:
    return hash(key) % shard_count

_MODULE_EXPORTS = {
    'compression': {'compress': 'runtime.platform.support.data:compress', 'decompress': 'runtime.platform.support.data:decompress'},
    'contracts': {'TrajectoryReader': 'runtime.platform.support.data:TrajectoryReader'},
    'data_catalog': {'DataCatalog': 'runtime.platform.support.data:DataCatalog'},
    'dataset_identity': {'DatasetIdentity': 'runtime.platform.support.data:DatasetIdentity'},
    'dataset_lineage': {'DatasetLineage': 'runtime.platform.support.data:DatasetLineage'},
    'dataset_loader': {'DatasetLoader': 'runtime.platform.support.data:DatasetLoader'},
    'dataset_registry': {'DatasetRegistry': 'runtime.platform.support.data:DatasetRegistry'},
    'dataset_versioning': {'DatasetVersioning': 'runtime.platform.support.data:DatasetVersioning'},
    'dataset_writer': {'DatasetWriter': 'runtime.platform.support.data:DatasetWriter'},
    'drift_checks': {'simple_drift': 'runtime.platform.support.data:simple_drift'},
    'integrity_checks': {'not_none': 'runtime.platform.support.data:not_none'},
    'partitioning': {'partition': 'runtime.platform.support.data:partition'},
    'quality_checks': {'trajectory_not_empty': 'runtime.platform.support.data:trajectory_not_empty'},
    'retention': {'RetentionPolicy': 'runtime.platform.support.data:RetentionPolicy'},
    'retention_policies': {'DEFAULT_RETENTION_DAYS': 'runtime.platform.support.data:DEFAULT_RETENTION_DAYS'},
    'sharding': {'shard_index': 'runtime.platform.support.data:shard_index'},
}

__all__ = [
    'DEFAULT_RETENTION_DAYS', 'DataCatalog', 'DatasetIdentity', 'DatasetLineage', 'DatasetLoader', 'DatasetRegistry',
    'DatasetVersioning', 'DatasetWriter', 'RetentionPolicy', 'TrajectoryReader', 'compress', 'decompress',
    'not_none', 'partition', 'shard_index', 'simple_drift', 'trajectory_not_empty',
]
