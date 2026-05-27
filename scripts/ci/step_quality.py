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

_CRITICAL_RUFF_SELECT = ("E9", "F63", "F7", "F82")


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
    return os.environ.get("BAIOS_REQUIRE_QUALITY_TOOLS", "").strip().lower() in {"1", "true", "yes", "release"}


def _strict_ruff_required() -> bool:
    return os.environ.get("BAIOS_REQUIRE_FULL_RUFF", "").strip().lower() in {"1", "true", "yes", "release"}


def _ruff_base_args(*, targets: tuple[Path, ...], config: Path) -> list[str]:
    args = [sys.executable, "-m", "ruff", "check", *(str(target) for target in targets)]
    if config.exists():
        args.extend(["--config", str(config)])
    return args


def _ruff_check() -> tuple[bool, str, dict[str, object]]:
    root = repo_root()
    targets = _quality_target_paths(root)
    config = root / "ruff.toml"
    payload: dict[str, object] = {
        "artifact": "quality_check",
        "ruff_available": False,
        "ruff_critical_select": list(_CRITICAL_RUFF_SELECT),
        "claims_full_ruff_clean": False,
        "claims_production_ready": False,
    }
    if not targets:
        payload["status"] = "blocked"
        payload["violations"] = ["quality_targets_missing"]
        return False, "quality targets missing", payload
    if importlib.util.find_spec("ruff") is None:
        payload["status"] = "blocked" if _quality_tools_required() else "advisory"
        payload["violations"] = ["ruff_unavailable"] if _quality_tools_required() else []
        if _quality_tools_required():
            return False, "ruff unavailable while BAIOS_REQUIRE_QUALITY_TOOLS is enabled", payload
        return True, "ruff unavailable in environment; skipped by non-release contract", payload

    payload["ruff_available"] = True
    critical_args = [*_ruff_base_args(targets=targets, config=config), "--select", ",".join(_CRITICAL_RUFF_SELECT)]
    critical = run_command(critical_args, env={"PYTHONNOUSERSITE": "1"}, timeout=180)
    payload["critical_ruff_passed"] = critical.returncode == 0
    if critical.returncode != 0:
        payload["status"] = "blocked"
        payload["violations"] = ["ruff_critical_baseline_failed"]
        return False, "ruff critical baseline failed", payload

    if _strict_ruff_required():
        strict = run_command(_ruff_base_args(targets=targets, config=config), env={"PYTHONNOUSERSITE": "1"}, timeout=180)
        payload["full_ruff_passed"] = strict.returncode == 0
        payload["claims_full_ruff_clean"] = strict.returncode == 0
        if strict.returncode != 0:
            payload["status"] = "blocked"
            payload["violations"] = ["full_ruff_strict_failed"]
            return False, "full ruff strict check failed", payload
        payload["status"] = "ready"
        return True, "ruff critical baseline and strict full check passed", payload

    payload["status"] = "ready_with_debt"
    payload["warnings"] = ["full_ruff_strict_not_enforced", "legacy_ruff_debt_present_or_unmeasured"]
    return True, "ruff critical baseline passed; full ruff strict debt is not claimed clean", payload


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
