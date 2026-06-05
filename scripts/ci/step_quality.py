from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
from pathlib import Path

from scripts.ci.config import project_shape_config
from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_command


_RUFF_REQUIRED_VALUES = {"1", "true", "yes", "release", "required", "strict", "on"}


def _iter_python_files(path: Path):
    if path.is_file() and path.suffix == ".py":
        yield path
        return
    if not path.exists():
        return
    for candidate in path.rglob("*.py"):
        parts = set(candidate.parts)
        if "__pycache__" in parts or ".venv" in parts or "venv" in parts:
            continue
        yield candidate


def _quality_target_paths(root: Path) -> tuple[Path, ...]:
    cfg = project_shape_config(root)
    return tuple(root / rel for rel in cfg.quality_targets)


def _artifact_path() -> Path:
    path = repo_root() / "artifacts" / "ci" / "quality_check.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _write_artifact(payload: dict[str, object]) -> None:
    _artifact_path().write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _syntax_check_targets() -> tuple[bool, str, int]:
    root = repo_root()
    cfg = project_shape_config(root)

    if not cfg.quality_targets:
        return False, "quality target set is empty", 0

    failed: list[str] = []
    checked = 0
    for rel in cfg.quality_targets:
        for path in _iter_python_files(root / rel):
            checked += 1
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                failed.append(f"{path.relative_to(root)}:{exc.lineno}:{exc.offset}: {exc.msg}")
            except UnicodeDecodeError as exc:
                failed.append(f"{path.relative_to(root)}: unicode decode error: {exc}")

    if failed:
        return False, "syntax check failed: " + "; ".join(failed[:20]), checked

    return True, f"syntax check passed for {checked} Python files", checked


def _quality_tools_required() -> bool:
    value = os.environ.get("BAIOS_REQUIRE_QUALITY_TOOLS", "").strip().lower()
    return value in _RUFF_REQUIRED_VALUES or not value


def _ruff_check() -> tuple[bool, str, dict[str, object]]:
    root = repo_root()
    targets = _quality_target_paths(root)
    config = root / "ruff.toml"
    payload: dict[str, object] = {
        "artifact": "quality_check",
        "ruff_available": False,
        "ruff_scope": "full_repository_quality_targets",
        "ruff_fail_closed": True,
        "claims_full_ruff_clean": False,
        "claims_legacy_ruff_debt_allowed": False,
        "claims_production_ready": False,
    }
    if not targets:
        payload["status"] = "blocked"
        payload["violations"] = ["quality_targets_missing"]
        return False, "quality targets missing", payload
    payload["ruff_targets"] = [str(path.relative_to(root)) for path in targets]
    if importlib.util.find_spec("ruff") is None:
        payload["status"] = "blocked" if _quality_tools_required() else "advisory"
        payload["violations"] = ["ruff_unavailable"] if _quality_tools_required() else []
        if _quality_tools_required():
            return False, "ruff unavailable while strict quality gate is enabled", payload
        return True, "ruff unavailable only because quality tools are explicitly non-required", payload

    payload["ruff_available"] = True
    args = [sys.executable, "-m", "ruff", "check", *(str(target) for target in targets)]
    if config.exists():
        args.extend(["--config", str(config)])

    outcome = run_command(args, env={"PYTHONNOUSERSITE": "1"}, timeout=180)
    passed = outcome.returncode == 0
    payload["full_ruff_passed"] = passed
    payload["claims_full_ruff_clean"] = passed
    if not passed:
        payload["status"] = "blocked"
        payload["violations"] = ["full_ruff_strict_failed"]
        return False, "full ruff strict check failed", payload

    payload["status"] = "ready"
    payload["violations"] = []
    return True, "full ruff strict check passed for repository quality targets", payload


def run() -> tuple[bool, str]:
    ok_syntax, msg_syntax, checked = _syntax_check_targets()
    payload: dict[str, object] = {
        "artifact": "quality_check",
        "syntax_checked_files": checked,
        "syntax_passed": ok_syntax,
        "claims_production_ready": False,
    }
    if not ok_syntax:
        payload["status"] = "blocked"
        payload["violations"] = ["syntax_check_failed"]
        _write_artifact(payload)
        return False, msg_syntax

    ok_ruff, msg_ruff, ruff_payload = _ruff_check()
    payload.update(ruff_payload)
    payload["syntax_checked_files"] = checked
    payload["syntax_passed"] = True
    _write_artifact(payload)
    if not ok_ruff:
        return False, msg_ruff

    return True, f"{msg_syntax}; {msg_ruff}"


__all__ = ["run"]
