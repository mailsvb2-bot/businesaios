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
_RATCHETED_STRICT_DEBT = (("deployment", "UP035"), ("headless", "I001,UP035"), ("infrastructure", "F401,I001,UP035"), ("leads", "I001"), ("mvp", "I001"), ("demand_decision", "I001"), ("ops", "E402,UP006,UP035"), ("crm", "F401"), ("contracts", "UP012"), ("demand_gravity", "F401"), ("ports", "E402"), ("presentation", "I001"), ("demand_learning", "I001"), ("demand_seo", "I001"), ("attribution", "I001,UP035,UP037"), ("release", "I001"), ("reliability", "F401"), ("scripts", "I001"), ("routing", "I001"), ("config", "I001"), ("guardrails", "F401"), ("governance", "F401"), ("analytics", "F401"), ("acquisition", "E402,F401,I001,SIM101,UP035,UP038"), ("formal", "F401"), ("ml", "F401"), ("supply_state", "F401"), ("supply_directory", "I001"), ("spend", "I001,UP034,UP035"), ("quality", "I001,UP035"), ("shared", "F401"), ("kernel", "F401"), ("infra", "F401"), ("tenancy", "F401"), ("boot", "F401"), ("learning", "F401"), ("intent", "I001"), ("application", "I001"), ("routing_execution", "I001"))


def _iter_python_files(path: Path):
    if path.is_file() and path.suffix == ".py":
        yield path
        return
    if not path.exists():
        return
    for candidate in path.rglob("*.py"):
        parts = set(candidate.parts)
        if "__pycache__" not in parts and ".venv" not in parts and "venv" not in parts:
            yield candidate


def _quality_target_paths(root: Path) -> tuple[Path, ...]:
    return tuple(root / rel for rel in project_shape_config(root).quality_targets)


def _artifact_path(name: str = "quality_check.json") -> Path:
    path = repo_root() / "artifacts" / "ci" / name
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


def _ruff_json_findings(args: list[str], *, timeout: int) -> tuple[list[dict[str, object]] | None, dict[str, object]]:
    outcome = run_command(args, env={"PYTHONNOUSERSITE": "1"}, timeout=timeout, echo_output=False)
    if outcome.returncode not in {0, 1}:
        return None, {"error": "ruff_command_failed", "returncode": outcome.returncode, "stderr": outcome.stderr[-2000:]}
    try:
        findings = json.loads(outcome.stdout.strip() or "[]")
    except json.JSONDecodeError:
        return None, {"error": "ruff_json_output_parse_failed"}
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        return None, {"error": "ruff_json_output_shape_invalid"}
    root = repo_root()
    normalized: list[dict[str, object]] = []
    for raw_item in findings:
        item = dict(raw_item)
        filename = str(item.get("filename") or "")
        try:
            item["filename"] = Path(filename).resolve().relative_to(root).as_posix()
        except ValueError:
            item["filename"] = filename
        normalized.append(item)
    return normalized, {}


def _targeted_debt_report(*, targets: tuple[Path, ...], config: Path) -> dict[str, object]:
    args = [*_ruff_base_args(targets=targets, config=config), "--select", ",".join(_TARGETED_STRICT_DEBT_SELECT), "--output-format", "json"]
    findings, error = _ruff_json_findings(args, timeout=180)
    base: dict[str, object] = {
        "targeted_strict_debt_select": list(_TARGETED_STRICT_DEBT_SELECT),
        "targeted_strict_debt_measured": findings is not None,
        "targeted_strict_debt_counts": {},
        "targeted_strict_debt_samples": [],
    }
    if findings is None:
        base.update({f"targeted_strict_debt_{key}": value for key, value in error.items()})
        return base
    counts = {code: 0 for code in _TARGETED_STRICT_DEBT_SELECT}
    samples: list[dict[str, object]] = []
    for item in findings:
        code = str(item.get("code") or "")
        if code not in counts:
            continue
        counts[code] += 1
        if len(samples) < _MAX_DEBT_SAMPLES:
            location = item.get("location") or {}
            samples.append({"code": code, "path": item.get("filename"), "row": location.get("row"), "column": location.get("column"), "message": item.get("message")})
    base.update({
        "targeted_strict_debt_counts": counts,
        "targeted_strict_debt_total": sum(counts.values()),
        "targeted_strict_debt_samples": samples,
        "targeted_strict_debt_sample_limit": _MAX_DEBT_SAMPLES,
    })
    return base


def _full_debt_report(*, config: Path) -> dict[str, object]:
    args = [sys.executable, "-m", "ruff", "check", ".", "--output-format", "json"]
    if config.exists():
        args.extend(["--config", str(config)])
    findings, error = _ruff_json_findings(args, timeout=300)
    if findings is None:
        return {"full_ruff_measured": False, **{f"full_ruff_{key}": value for key, value in error.items()}}
    by_rule: dict[str, int] = {}
    by_package: dict[str, int] = {}
    for item in findings:
        code = str(item.get("code") or "unknown")
        path = str(item.get("filename") or "")
        package = path.split("/", 1)[0] if "/" in path else "(root)"
        by_rule[code] = by_rule.get(code, 0) + 1
        by_package[package] = by_package.get(package, 0) + 1
    report_path = _artifact_path("ruff_full.json")
    report_path.write_text(json.dumps(findings, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "full_ruff_measured": True,
        "full_ruff_total": len(findings),
        "full_ruff_counts_by_rule": dict(sorted(by_rule.items())),
        "full_ruff_counts_by_package": dict(sorted(by_package.items())),
        "full_ruff_report_path": report_path.relative_to(repo_root()).as_posix(),
    }


def _ruff_check() -> tuple[bool, str, dict[str, object]]:
    root = repo_root()
    targets = _quality_target_paths(root)
    config = root / "ruff.toml"
    payload: dict[str, object] = {
        "artifact": "quality_check", "ruff_available": False,
        "ruff_critical_select": list(_CRITICAL_RUFF_SELECT), "claims_full_ruff_clean": False,
        "claims_production_ready": False, "targeted_strict_debt_enforced": True,
    }
    if not targets:
        payload.update(status="blocked", violations=["quality_targets_missing"])
        return False, "quality targets missing", payload
    if importlib.util.find_spec("ruff") is None:
        required = _quality_tools_required()
        payload.update(status="blocked" if required else "advisory", violations=["ruff_unavailable"] if required else [])
        return (False, "ruff unavailable while BAIOS_REQUIRE_QUALITY_TOOLS is enabled", payload) if required else (True, "ruff unavailable in environment; skipped by non-release contract", payload)
    payload["ruff_available"] = True
    critical = run_command([*_ruff_base_args(targets=targets, config=config), "--select", ",".join(_CRITICAL_RUFF_SELECT)], env={"PYTHONNOUSERSITE": "1"}, timeout=180)
    payload["critical_ruff_passed"] = critical.returncode == 0
    if critical.returncode != 0:
        payload.update(status="blocked", violations=["ruff_critical_baseline_failed"])
        return False, "ruff critical baseline failed", payload
    payload.update(_targeted_debt_report(targets=targets, config=config))
    payload.update(_full_debt_report(config=config))
    if not payload.get("full_ruff_measured"):
        payload.update(status="blocked", violations=["full_ruff_inventory_failed"])
        return False, "full ruff inventory failed", payload
    targeted_clean = bool(payload.get("targeted_strict_debt_measured")) and int(payload.get("targeted_strict_debt_total") or 0) == 0
    payload["targeted_strict_debt_clean"] = targeted_clean
    if not targeted_clean:
        payload.update(status="blocked", violations=["targeted_strict_debt_lock_failed"])
        return False, "targeted strict ruff debt lock failed", payload
    for package, select in _RATCHETED_STRICT_DEBT:
        ratchet = run_command([*_ruff_base_args(targets=(root / package,), config=config), "--select", select], env={"PYTHONNOUSERSITE": "1"}, timeout=180)
        payload[f"{package}_{select.lower()}_passed"] = ratchet.returncode == 0
        if ratchet.returncode != 0:
            payload.update(status="blocked", violations=[f"{package}_{select.lower()}_ratchet_failed"])
            return False, f"{package} {select} ruff ratchet failed", payload
    full_clean = int(payload.get("full_ruff_total") or 0) == 0
    payload.update(full_ruff_passed=full_clean, claims_full_ruff_clean=full_clean)
    if _strict_ruff_required():
        if not full_clean:
            payload.update(status="blocked", violations=["full_ruff_strict_failed"])
            return False, "full ruff strict check failed", payload
        payload["status"] = "ready"
        return True, "ruff critical baseline, targeted strict lock, and strict full check passed", payload
    payload.update(status="ready_with_unenforced_full_ruff", warnings=["full_ruff_strict_not_enforced"])
    return True, f"ruff critical baseline and targeted strict lock passed; inventoried {payload['full_ruff_total']} full ruff findings", payload


def run() -> tuple[bool, str]:
    ok_syntax, msg_syntax, checked = _syntax_check_targets()
    payload: dict[str, object] = {"artifact": "quality_check", "syntax_checked_files": checked, "syntax_passed": ok_syntax, "claims_production_ready": False}
    if not ok_syntax:
        payload.update(status="blocked", violations=["syntax_check_failed"])
        _write_artifact(payload)
        return False, msg_syntax
    ok_ruff, msg_ruff, ruff_payload = _ruff_check()
    payload.update(ruff_payload)
    payload.update(syntax_checked_files=checked, syntax_passed=True)
    _write_artifact(payload)
    return (False, msg_ruff) if not ok_ruff else (True, f"{msg_syntax}; {msg_ruff}")


__all__ = ["run"]
