from __future__ import annotations
CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_CLUSTER_FINAL_OWNER = True


from pathlib import Path
from typing import Any, Dict

from runtime.boot.env import env_bool

from bootstrap.world_model_boot_check import verify_boot_world_model_integrity
from bootstrap.world_model_forbidden_paths import scan_repo_for_forbidden_world_model_paths


class WorldModelSelfCheckError(RuntimeError):
    pass


def run_world_model_self_check(
    *,
    world_model: Any,
    repo_root: str | Path,
) -> Dict[str, Any]:
    integrity = verify_boot_world_model_integrity(world_model=world_model)
    findings = scan_repo_for_forbidden_world_model_paths(repo_root=repo_root)

    result = {
        "integrity": integrity,
        "forbidden_paths": findings,
        "ok": bool(integrity.get("ok")) and not findings,
    }

    if not result["ok"] and is_world_model_self_check_strict():
        raise WorldModelSelfCheckError(
            f"world model self-check failed: forbidden_paths={len(findings)}"
        )

    return result


def is_world_model_self_check_strict() -> bool:
    return env_bool("STRICT_WORLD_MODEL_SELF_CHECK", True)
