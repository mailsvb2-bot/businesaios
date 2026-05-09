from __future__ import annotations

import ast
from pathlib import Path

from scripts.ci.config import project_shape_config
from scripts.ci.step_ids import all_step_names

CANON_CI_WORKFLOW_ENTRYPOINTS = (
    "python -m scripts.ci.cli --gate",
    "python scripts/ci/cli.py --gate",
)


def python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def find_empty_ci_files(root: Path) -> list[str]:
    offenders: list[str] = []
    ci_root = root / "scripts" / "ci"
    for path in python_files(ci_root):
        if path.stat().st_size == 0:
            offenders.append(path.relative_to(root).as_posix())
    return offenders


def find_second_execution_imports(root: Path) -> list[str]:
    offenders: list[str] = []
    ci_root = root / "scripts" / "ci"
    for path in python_files(ci_root):
        if path.name == "execution.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "scripts.ci.execution":
                if path.name != "cli.py":
                    offenders.append(path.relative_to(root).as_posix())
                    break
    return offenders


def find_second_plan_order_definitions(root: Path) -> list[str]:
    offenders: list[str] = []
    ci_root = root / "scripts" / "ci"
    sentinel_names = all_step_names()
    for path in python_files(ci_root):
        if path.name == "plan_registry.py":
            continue
        text = path.read_text(encoding="utf-8")
        hits = sum(1 for name in sentinel_names if name in text)
        if hits >= 3:
            offenders.append(path.relative_to(root).as_posix())
    return offenders


def looks_like_shell_script(path: Path) -> bool:
    if path.suffix == ".sh":
        return True
    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
    except (IndexError, UnicodeDecodeError):
        return False
    return first_line.startswith("#!") and ("sh" in first_line or "bash" in first_line)


def find_unapproved_ci_shell_files(root: Path) -> list[str]:
    cfg = project_shape_config(root)
    allowed = set(cfg.allowed_ci_shell_files)
    shell_files: list[str] = []
    for rel_root in ("ci", ".githooks"):
        base = root / rel_root
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if looks_like_shell_script(path):
                shell_files.append(path.relative_to(root).as_posix())
    return [rel for rel in shell_files if rel not in allowed]


def find_workflows_without_single_entrypoint(root: Path) -> list[str]:
    cfg = project_shape_config(root)
    offenders: list[str] = []
    for rel in cfg.allowed_workflows:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if rel.endswith("docker-image.yml"):
            continue
        if not any(entrypoint in text for entrypoint in CANON_CI_WORKFLOW_ENTRYPOINTS):
            offenders.append(rel)
    return offenders


def find_domain_coupling(root: Path) -> list[str]:
    forbidden_prefixes = (
        "core.ai.decision_core",
        "runtime.boot",
        "runtime.executor",
        "runtime.guard",
        "interfaces.telegram",
        "interfaces.web",
    )
    offenders: list[str] = []
    ci_root = root / "scripts" / "ci"
    for path in python_files(ci_root):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        bad = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module] if node.module else []
            else:
                continue

            for name in names:
                if any(name.startswith(prefix) for prefix in forbidden_prefixes):
                    bad = True
                    break
            if bad:
                offenders.append(path.relative_to(root).as_posix())
                break
    return offenders
