from __future__ import annotations

import json
from pathlib import Path

PRODUCTION_READINESS_ARTIFACTS = (
    "postgres_contract.json",
    "postgres_migrations.json",
    "postgres_live.json",
    "production_boot.json",
    "container_runtime.json",
)


def _read_artifact(root: Path, name: str) -> dict[str, object]:
    path = root / "artifacts" / "ci" / name
    artifact_name = name.removesuffix(".json")
    if not path.exists():
        return {"artifact": artifact_name, "status": "missing", "claims_production_ready": False}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"artifact": artifact_name, "status": "invalid", "claims_production_ready": False}
    payload.setdefault("claims_production_ready", False)
    return dict(payload)


def build_production_readiness_admin_view(root: Path | None = None) -> dict[str, object]:
    base = root or Path.cwd()
    artifacts = {name.removesuffix(".json"): _read_artifact(base, name) for name in PRODUCTION_READINESS_ARTIFACTS}
    return {
        "surface": "production_readiness",
        "status": "observable",
        "artifacts": artifacts,
        "claims_production_ready": False,
    }


__all__ = ["PRODUCTION_READINESS_ARTIFACTS", "build_production_readiness_admin_view"]
