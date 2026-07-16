"""Runtime integrity checks for the canonical world model.

Repository source-policy scanning belongs to CI and operator diagnostics. Runtime
boot validates the constructed world-model object without walking the checkout by
default; an explicit environment flag can enable the source scan for diagnostics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bootstrap.world_model_boot_check import verify_boot_world_model_integrity
from bootstrap.world_model_forbidden_paths import scan_repo_for_forbidden_world_model_paths
from runtime.boot.env import env_bool

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True


class WorldModelSelfCheckError(RuntimeError):
    pass


def run_world_model_self_check(
    *,
    world_model: Any,
    repo_root: str | Path,
    scan_source: bool | None = None,
) -> dict[str, Any]:
    integrity = verify_boot_world_model_integrity(world_model=world_model)
    source_scan_enabled = (
        is_world_model_source_scan_on_boot_enabled()
        if scan_source is None
        else bool(scan_source)
    )
    findings = (
        scan_repo_for_forbidden_world_model_paths(repo_root=repo_root)
        if source_scan_enabled
        else []
    )

    result = {
        "integrity": integrity,
        "forbidden_paths": findings,
        "source_scan_enabled": source_scan_enabled,
        "ok": bool(integrity.get("ok")) and not findings,
    }

    if not result["ok"] and is_world_model_self_check_strict():
        raise WorldModelSelfCheckError(
            f"world model self-check failed: forbidden_paths={len(findings)}"
        )

    return result


def is_world_model_source_scan_on_boot_enabled() -> bool:
    return env_bool("WORLD_MODEL_SOURCE_SCAN_ON_BOOT", False)


def is_world_model_self_check_strict() -> bool:
    return env_bool("STRICT_WORLD_MODEL_SELF_CHECK", True)
