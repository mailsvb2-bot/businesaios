from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": str(self.model_id),
            "snapshot_id": str(self.snapshot_id),
            "algo": str(self.algo),
            "metrics": {str(k): float(v) for k, v in dict(self.metrics).items()},
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ModelArtifact":
        return cls(
            model_id=str(payload.get("model_id") or ""),
            snapshot_id=str(payload.get("snapshot_id") or ""),
            algo=str(payload.get("algo") or ""),
            metrics={str(k): float(v) for k, v in dict(payload.get("metrics") or {}).items()},
            payload=dict(payload.get("payload") or {}),
        )


@dataclass(frozen=True)
class ValidatedModelRecord:
    model_id: str
    snapshot_id: str
    algo: str
    candidate_policy_id: str
    metrics: Dict[str, float]
    payload: Dict[str, Any]
    validation: Dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": str(self.model_id),
            "snapshot_id": str(self.snapshot_id),
            "algo": str(self.algo),
            "candidate_policy_id": str(self.candidate_policy_id),
            "metrics": {str(k): float(v) for k, v in dict(self.metrics).items()},
            "payload": dict(self.payload),
            "validation": dict(self.validation),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ValidatedModelRecord":
        return cls(
            model_id=str(payload.get("model_id") or ""),
            snapshot_id=str(payload.get("snapshot_id") or ""),
            algo=str(payload.get("algo") or ""),
            candidate_policy_id=str(payload.get("candidate_policy_id") or ""),
            metrics={str(k): float(v) for k, v in dict(payload.get("metrics") or {}).items()},
            payload=dict(payload.get("payload") or {}),
            validation=dict(payload.get("validation") or {}),
        )


def _candidate_policy_id_from_artifact(model: ModelArtifact, explicit: str | None = None) -> str:
    candidate = str(explicit or "").strip()
    if candidate:
        return candidate
    for key in ("candidate_policy_id", "best_policy_id", "policy_id"):
        candidate = str(model.payload.get(key) or "").strip()
        if candidate:
            return candidate
    return str(model.model_id).strip()


def _validated_record_for(
    *,
    model: ModelArtifact,
    candidate_policy_id: str | None = None,
    validation: Dict[str, Any] | None = None,
) -> ValidatedModelRecord:
    return ValidatedModelRecord(
        model_id=str(model.model_id),
        snapshot_id=str(model.snapshot_id),
        algo=str(model.algo),
        candidate_policy_id=_candidate_policy_id_from_artifact(model, candidate_policy_id),
        metrics=dict(model.metrics),
        payload=dict(model.payload),
        validation=dict(validation or {}),
    )


class ArtifactRegistry:
    """In-memory model registry for tests/dev offline jobs.

    It implements the same validation contract as the file-backed ModelRegistry.
    """

    def __init__(self) -> None:
        self._models: Dict[str, ModelArtifact] = {}
        self._latest_validated: ValidatedModelRecord | None = None

    def register_artifact(
        self,
        *,
        snapshot_id: str,
        algo: str,
        metrics: Dict[str, float],
        payload: Dict[str, Any],
    ) -> ModelArtifact:
        model_id = _stable_hash({"snapshot_id": snapshot_id, "algo": algo, "metrics": metrics, "payload": payload})
        art = ModelArtifact(
            model_id=model_id,
            snapshot_id=str(snapshot_id),
            algo=str(algo),
            metrics=dict(metrics),
            payload=dict(payload),
        )
        self._models[model_id] = art
        return art

    def register(
        self,
        *,
        snapshot_id: str,
        algo: str,
        metrics: Dict[str, float],
        payload: Dict[str, Any],
    ) -> ModelArtifact:
        return self.register_artifact(snapshot_id=snapshot_id, algo=algo, metrics=metrics, payload=payload)

    def get(self, model_id: str) -> Optional[ModelArtifact]:
        return self._models.get(str(model_id))

    def mark_validated(
        self,
        *,
        model: ModelArtifact,
        candidate_policy_id: str | None = None,
        validation: Dict[str, Any] | None = None,
    ) -> ValidatedModelRecord:
        normalized = model if isinstance(model, ModelArtifact) else ModelArtifact.from_dict(dict(model))
        self._models[str(normalized.model_id)] = normalized
        record = _validated_record_for(model=normalized, candidate_policy_id=candidate_policy_id, validation=validation)
        self._latest_validated = record
        return record

    def latest_validated(self) -> ValidatedModelRecord | None:
        return self._latest_validated


class SupportsModelRegistry(Protocol):
    def register_artifact(
        self,
        *,
        snapshot_id: str,
        algo: str,
        metrics: Dict[str, float],
        payload: Dict[str, Any],
    ) -> ModelArtifact: ...

    def mark_validated(
        self,
        *,
        model: ModelArtifact,
        candidate_policy_id: str | None = None,
        validation: Dict[str, Any] | None = None,
    ) -> ValidatedModelRecord: ...

    def latest_validated(self) -> ValidatedModelRecord | None: ...
    def register(self, model_path: Path) -> None: ...
    def activate(self, model_id: str) -> None: ...
    def get_active_model_id(self) -> str | None: ...
    def get_active_policy(self) -> Dict[str, float]: ...


class ModelRegistry:
    """File-backed model registry with explicit validated-candidate contract.

    This is intentionally independent from durable Postgres event/ledger/archive
    storage. It is a model-artifact registry, not a hidden runtime fallback path.
    """

    def __init__(self, dir_path: Path):
        self.dir = Path(dir_path)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.active_file = self.dir / "ACTIVE"
        self._artifacts_dir = self.dir / "artifacts"
        self._artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._latest_validated_file = self.dir / "LATEST_VALIDATED.json"

    def register(self, model_path: Path) -> None:
        model_path = Path(model_path)
        target = self.dir / model_path.name
        target.write_bytes(model_path.read_bytes())

    def register_artifact(
        self,
        *,
        snapshot_id: str,
        algo: str,
        metrics: Dict[str, float],
        payload: Dict[str, Any],
    ) -> ModelArtifact:
        model_id = _stable_hash({"snapshot_id": snapshot_id, "algo": algo, "metrics": metrics, "payload": payload})
        art = ModelArtifact(
            model_id=model_id,
            snapshot_id=str(snapshot_id),
            algo=str(algo),
            metrics=dict(metrics),
            payload=dict(payload),
        )
        artifact_path = self._artifacts_dir / f"{art.model_id}.json"
        artifact_path.write_text(json.dumps(art.to_dict(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return art

    def get(self, model_id: str) -> Optional[ModelArtifact]:
        artifact_path = self._artifacts_dir / f"{str(model_id).strip()}.json"
        if not artifact_path.exists():
            return None
        return ModelArtifact.from_dict(json.loads(artifact_path.read_text(encoding="utf-8")))

    def mark_validated(
        self,
        *,
        model: ModelArtifact,
        candidate_policy_id: str | None = None,
        validation: Dict[str, Any] | None = None,
    ) -> ValidatedModelRecord:
        normalized = model if isinstance(model, ModelArtifact) else ModelArtifact.from_dict(dict(model))
        artifact_path = self._artifacts_dir / f"{normalized.model_id}.json"
        if not artifact_path.exists():
            artifact_path.write_text(json.dumps(normalized.to_dict(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
        record = _validated_record_for(model=normalized, candidate_policy_id=candidate_policy_id, validation=validation)
        self._latest_validated_file.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return record

    def latest_validated(self) -> ValidatedModelRecord | None:
        if not self._latest_validated_file.exists():
            return None
        raw = json.loads(self._latest_validated_file.read_text(encoding="utf-8"))
        record = ValidatedModelRecord.from_dict(raw)
        return record if record.candidate_policy_id else None

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
    "ValidatedModelRecord",
    "build_model_registry",
]
