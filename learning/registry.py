from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol
import hashlib
import json

from runtime.platform.config.env_flags import env_path, env_str


MODEL_REGISTRY_BACKEND_ENV = "MODEL_REGISTRY_BACKEND"
MODEL_REGISTRY_BACKEND_SQLITE = "sqlite"
MODEL_REGISTRY_BACKEND_POSTGRES = "postgres"


def _stable_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ModelArtifact:
    model_id: str
    snapshot_id: str
    algo: str
    metrics: Dict[str, float]
    payload: Dict[str, Any]


class ArtifactRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, ModelArtifact] = {}

    def register(self, *, snapshot_id: str, algo: str, metrics: Dict[str, float], payload: Dict[str, Any]) -> ModelArtifact:
        model_id = _stable_hash({"snapshot_id": snapshot_id, "algo": algo, "metrics": metrics, "payload": payload})
        art = ModelArtifact(model_id=model_id, snapshot_id=str(snapshot_id), algo=str(algo), metrics=dict(metrics), payload=dict(payload))
        self._models[model_id] = art
        return art

    def get(self, model_id: str) -> Optional[ModelArtifact]:
        return self._models.get(str(model_id))


class SupportsModelRegistry(Protocol):
    def register(self, model_path: Path) -> None: ...
    def activate(self, model_id: str) -> None: ...
    def get_active_model_id(self) -> str | None: ...
    def get_active_policy(self) -> Dict[str, float]: ...


class ModelRegistry:
    def __init__(self, dir_path: Path):
        self.dir = Path(dir_path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.active_file = self.dir / "ACTIVE"

    def register(self, model_path: Path) -> None:
        model_path = Path(model_path)
        target = self.dir / model_path.name
        target.write_bytes(model_path.read_bytes())

    def activate(self, model_id: str) -> None:
        self.active_file.write_text(str(model_id), encoding="utf-8")

    def get_active_model_id(self) -> str | None:
        if not self.active_file.exists():
            return None
        model_id = self.active_file.read_text(encoding="utf-8").strip()
        return model_id or None

    def get_active_policy(self) -> Dict[str, float]:
        model_id = self.get_active_model_id()
        if not model_id:
            return {}
        path = self.dir / f"{model_id}.json"
        if not path.exists():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
        out: Dict[str, float] = {}
        for k, v in (raw or {}).items():
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
        return out


def _model_registry_backend() -> str:
    """Resolve ML model registry backend independently from durable storage.

    Durable runtime storage may use Postgres while the ML model registry remains
    file-backed. The disabled PostgresModelRegistry must never be selected merely
    because POSTGRES_DSN is configured for event/ledger/archive storage.
    """
    backend = (env_str(MODEL_REGISTRY_BACKEND_ENV, MODEL_REGISTRY_BACKEND_SQLITE) or MODEL_REGISTRY_BACKEND_SQLITE).strip().lower()
    return backend or MODEL_REGISTRY_BACKEND_SQLITE


def build_model_registry() -> SupportsModelRegistry:
    backend = _model_registry_backend()
    if backend == MODEL_REGISTRY_BACKEND_POSTGRES:
        dsn = env_str("MODEL_REGISTRY_POSTGRES_DSN", "") or env_str("POSTGRES_DSN", "") or None
        if not dsn:
            raise RuntimeError("MODEL_REGISTRY_POSTGRES_REQUIRES_DSN")
        from runtime.platform.ml.postgres_model_registry import PostgresModelRegistry
        return PostgresModelRegistry(dsn)
    if backend != MODEL_REGISTRY_BACKEND_SQLITE:
        raise RuntimeError(f"UNKNOWN_MODEL_REGISTRY_BACKEND:{backend}")
    dir_path = env_path("MODEL_REGISTRY_DIR", "./data/ml_models")
    return ModelRegistry(dir_path)


__all__ = [
    "ArtifactRegistry",
    "MODEL_REGISTRY_BACKEND_ENV",
    "MODEL_REGISTRY_BACKEND_POSTGRES",
    "MODEL_REGISTRY_BACKEND_SQLITE",
    "ModelArtifact",
    "ModelRegistry",
    "SupportsModelRegistry",
    "build_model_registry",
]
