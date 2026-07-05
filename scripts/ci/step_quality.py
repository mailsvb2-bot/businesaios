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
_TARGETED_STRICT_DEBT_SELECT = ("E402", "F401", "UP035")
_MAX_DEBT_SAMPLES = 50


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


def _targeted_debt_report(*, targets: tuple[Path, ...], config: Path) -> dict[str, object]:
    args = [
        *_ruff_base_args(targets=targets, config=config),
        "--select",
        ",".join(_TARGETED_STRICT_DEBT_SELECT),
        "--output-format",
        "json",
    ]
    outcome = run_command(args, env={"PYTHONNOUSERSITE": "1"}, timeout=180)
    raw = outcome.stdout.strip() or "[]"
    try:
        findings = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "targeted_strict_debt_select": list(_TARGETED_STRICT_DEBT_SELECT),
            "targeted_strict_debt_measured": False,
            "targeted_strict_debt_counts": {},
            "targeted_strict_debt_samples": [],
            "targeted_strict_debt_error": "ruff_json_output_parse_failed",
        }
    counts = {code: 0 for code in _TARGETED_STRICT_DEBT_SELECT}
    samples: list[dict[str, object]] = []
    root = repo_root()
    for item in findings:
        code = str(item.get("code") or "")
        if code not in counts:
            continue
        counts[code] += 1
        if len(samples) >= _MAX_DEBT_SAMPLES:
            continue
        filename = str(item.get("filename") or "")
        try:
            path = Path(filename).resolve().relative_to(root).as_posix()
        except ValueError:
            path = filename
        location = item.get("location") or {}
        samples.append(
            {
                "code": code,
                "path": path,
                "row": location.get("row"),
                "column": location.get("column"),
                "message": item.get("message"),
            }
        )
    return {
        "targeted_strict_debt_select": list(_TARGETED_STRICT_DEBT_SELECT),
        "targeted_strict_debt_measured": True,
        "targeted_strict_debt_counts": counts,
        "targeted_strict_debt_total": sum(counts.values()),
        "targeted_strict_debt_samples": samples,
        "targeted_strict_debt_sample_limit": _MAX_DEBT_SAMPLES,
    }


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

    payload.update(_targeted_debt_report(targets=targets, config=config))

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

    targeted_measured = bool(payload.get("targeted_strict_debt_measured"))
    targeted_total = int(payload.get("targeted_strict_debt_total") or 0)
    if targeted_measured and targeted_total == 0:
        payload["status"] = "ready_with_unenforced_full_ruff"
        payload["targeted_strict_debt_clean"] = True
        payload["warnings"] = ["full_ruff_strict_not_enforced"]
        return True, "ruff critical baseline passed; targeted strict debt clean; full ruff strict check is not enforced", payload

    payload["status"] = "ready_with_debt"
    payload["targeted_strict_debt_clean"] = False
    payload["warnings"] = ["full_ruff_strict_not_enforced", "legacy_ruff_debt_present_or_unmeasured"]
    return True, "ruff critical baseline passed; targeted strict debt remains or was not measured", payload


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
