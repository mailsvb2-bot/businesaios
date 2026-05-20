from __future__ import annotations

from scripts.ci.config import project_shape_config
from scripts.ci.paths import repo_root


def run() -> tuple[bool, str]:
    root = repo_root()
    cfg = project_shape_config(root)
    missing = [rel for rel in cfg.required_paths if not (root / rel).exists()]
    if missing:
        return False, f"missing required paths: {missing}"

    workflow_dir = root / ".github" / "workflows"
    if workflow_dir.exists():
        actual_workflows = tuple(sorted(path.relative_to(root).as_posix() for path in workflow_dir.glob("*.yml")))
        allowed_workflows = tuple(sorted(cfg.allowed_workflows))
        if actual_workflows != allowed_workflows:
            return False, f"workflow contract drift: actual={actual_workflows} allowed={allowed_workflows}"

    return True, "project shape contract satisfied"


__all__ = ["run"]