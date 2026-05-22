from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "release" / "manifest.json"


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest() -> dict[str, object]:
    base_image = os.getenv("BAIOS_PYTHON_BASE_IMAGE", "businesaios/python-runtime-base:3.12-slim")
    dockerfile = ROOT / "Dockerfile"
    requirements = ROOT / "requirements.lock.txt"
    payload: dict[str, object] = {
        "artifact": "businesaios_staging_release_manifest",
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "app_profile": os.getenv("APP_PROFILE", "api"),
        "env": os.getenv("ENV", os.getenv("APP_ENV", "production")),
        "container": {
            "base_image": base_image,
            "base_image_pull_policy": "never_during_staging_proof",
            "dockerfile_sha256": _file_sha256(dockerfile) if dockerfile.exists() else None,
        },
        "dependencies": {
            "requirements_lock_sha256": _file_sha256(requirements) if requirements.exists() else None,
        },
        "proof": {
            "postgres_contract_required": True,
            "postgres_migrations_required": True,
            "postgres_live_required": True,
            "container_runtime_required": True,
            "production_boot_required": True,
        },
        "claims_production_ready": False,
    }
    return payload


def write_manifest() -> Path:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(build_manifest(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return MANIFEST


def main() -> int:
    path = write_manifest()
    print(path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
