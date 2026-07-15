from __future__ import annotations

import json
import sys
from dataclasses import dataclass

from scripts.ci.paths import coverage_dir, repo_root
from scripts.ci.subprocess_io import PYTEST_REQUIRED_PLUGINS, run_command

MIN_TOTAL_COVERAGE = 60.0
TARGET_TOTAL_COVERAGE = 70.0
PYTEST_COVERAGE_MARK = "not slow and not gate"

COVERAGE_TARGETS = (
    "tests/unit",
    "tests/core",
    "tests/security",
    "tests/growth",
    "tests/growth_strategy",
    "tests/autopilot",
    "tests/ads_autopilot",
    "tests/core/product",
    "tests/core/experiments",
    "tests/integration",
    "tests/runtime",
    "tests/interfaces",
    "tests/business_critical",
)

HEADLESS_SMOKE_TESTS = (
    "tests/integration/headless/test_cli_run_smoke.py",
    "tests/integration/headless/test_cli_scenario_smoke.py",
    "tests/integration/headless/test_sdk_execute_smoke.py",
)


@dataclass(frozen=True)
class CoverageShard:
    name: str
    timeout: int
    targets: tuple[str, ...]
    extra_pytest_args: tuple[str, ...] = ()


COVERAGE_SHARDS = (
    CoverageShard(
        name="unit",
        timeout=1200,
        targets=("tests/unit",),
    ),
    CoverageShard(
        name="domain-core-and-security",
        timeout=180,
        targets=(
            "tests/core",
            "tests/security",
            "tests/growth",
            "tests/growth_strategy",
            "tests/autopilot",
            "tests/ads_autopilot",
            "tests/core/product",
            "tests/core/experiments",
        ),
    ),
    CoverageShard(
        name="integration-core",
        timeout=1200,
        targets=("tests/integration",),
        extra_pytest_args=tuple(f"--ignore={path}" for path in HEADLESS_SMOKE_TESTS),
    ),
    CoverageShard(
        name="integration-headless-cli-run",
        timeout=240,
        targets=("tests/integration/headless/test_cli_run_smoke.py",),
    ),
    CoverageShard(
        name="integration-headless-cli-scenario",
        timeout=240,
        targets=("tests/integration/headless/test_cli_scenario_smoke.py",),
    ),
    CoverageShard(
        name="integration-headless-sdk-execute",
        timeout=240,
        targets=("tests/integration/headless/test_sdk_execute_smoke.py",),
    ),
    CoverageShard(
        name="runtime-and-interfaces",
        timeout=300,
        targets=("tests/runtime", "tests/interfaces"),
    ),
    CoverageShard(
        name="business-critical",
        timeout=180,
        targets=("tests/business_critical",),
    ),
)


def _coverage_paths():
    root = coverage_dir()
    return {
        "json": root / "coverage.json",
        "xml": root / "coverage.xml",
        "html": root / "html",
        "summary": root / "coverage_summary.json",
    }


def _python_command(*args: str) -> list[str]:
    return [sys.executable, *args]


def _write_summary(payload: dict[str, object]) -> None:
    path = _coverage_paths()["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _coverage_available() -> bool:
    outcome = run_command(_python_command("-c", "import coverage; print(coverage.__version__)"), timeout=20)
    return outcome.returncode == 0


def _pytest_plugin_args() -> list[str]:
    plugin_args: list[str] = []
    for plugin in PYTEST_REQUIRED_PLUGINS:
        plugin_args.extend(["-p", plugin])
    return plugin_args


def _coverage_warnings(percent: float) -> list[str]:
    warnings: list[str] = []
    if percent < TARGET_TOTAL_COVERAGE:
        warnings.append("coverage_below_target")
    return warnings


def _coverage_run_command(shard: CoverageShard) -> list[str]:
    return [
        *_python_command("-m", "scripts.ci.coverage_pytest_runner"),
        *_pytest_plugin_args(),
        "-q",
        *shard.targets,
        *shard.extra_pytest_args,
        "-m",
        PYTEST_COVERAGE_MARK,
    ]


def run() -> tuple[bool, str]:
    paths = _coverage_paths()
    if not _coverage_available():
        payload = {
            "artifact": "code_coverage",
            "status": "blocked",
            "coverage_kind": "coverage.py",
            "violations": ["coverage_py_required"],
            "warnings": [],
            "claims_code_coverage": False,
            "claims_production_ready": False,
        }
        _write_summary(payload)
        return False, "coverage.py is required for code coverage gate"

    erase = run_command(_python_command("-m", "coverage", "erase"), timeout=30)
    if erase.returncode != 0:
        _write_summary({
            "artifact": "code_coverage",
            "status": "blocked",
            "violations": ["coverage_erase_failed"],
            "warnings": [],
            "claims_code_coverage": False,
            "claims_production_ready": False,
        })
        return False, "coverage erase failed"

    completed_shards: list[str] = []
    for shard in COVERAGE_SHARDS:
        run_cov = run_command(
            _coverage_run_command(shard),
            env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONNOUSERSITE": "1"},
            timeout=shard.timeout,
        )
        if run_cov.returncode != 0:
            payload = {
                "artifact": "code_coverage",
                "status": "blocked",
                "coverage_kind": "coverage.py",
                "violations": ["coverage_pytest_failed"],
                "warnings": [],
                "targets": list(COVERAGE_TARGETS),
                "shards": [item.name for item in COVERAGE_SHARDS],
                "completed_shards": completed_shards,
                "failed_shard": shard.name,
                "failed_shard_targets": list(shard.targets),
                "claims_code_coverage": True,
                "claims_production_ready": False,
            }
            _write_summary(payload)
            return False, f"coverage pytest run failed in shard={shard.name}"
        completed_shards.append(shard.name)

    combine = run_command(_python_command("-m", "coverage", "combine"), timeout=60)
    if combine.returncode != 0:
        payload = {
            "artifact": "code_coverage",
            "status": "blocked",
            "coverage_kind": "coverage.py",
            "violations": ["coverage_combine_failed"],
            "warnings": [],
            "targets": list(COVERAGE_TARGETS),
            "shards": [item.name for item in COVERAGE_SHARDS],
            "completed_shards": completed_shards,
            "claims_code_coverage": True,
            "claims_production_ready": False,
        }
        _write_summary(payload)
        return False, "coverage combine failed"

    json_outcome = run_command(_python_command("-m", "coverage", "json", "-o", str(paths["json"])), timeout=60)
    xml_outcome = run_command(_python_command("-m", "coverage", "xml", "-o", str(paths["xml"])), timeout=60)
    html_outcome = run_command(_python_command("-m", "coverage", "html", "-d", str(paths["html"])), timeout=120)
    report_outcome = run_command(_python_command("-m", "coverage", "report", "--fail-under", str(MIN_TOTAL_COVERAGE)), timeout=60)

    coverage_payload = json.loads(paths["json"].read_text(encoding="utf-8")) if paths["json"].exists() else {}
    total = dict(coverage_payload.get("totals") or {})
    percent = float(total.get("percent_covered", 0.0))
    status = "ready" if report_outcome.returncode == 0 else "blocked"
    violations = [] if status == "ready" else ["coverage_below_minimum"]
    if json_outcome.returncode != 0:
        violations.append("coverage_json_failed")
    if xml_outcome.returncode != 0:
        violations.append("coverage_xml_failed")
    if html_outcome.returncode != 0:
        violations.append("coverage_html_failed")
    warnings = _coverage_warnings(percent)
    payload = {
        "artifact": "code_coverage",
        "status": status if not violations else "blocked",
        "coverage_kind": "coverage.py",
        "coverage_scope": "repo-wide coverage.py measurement for alpha baseline; target remains advisory until the repo reaches release coverage closure",
        "line_percent_covered": percent,
        "branch_coverage_enabled": True,
        "minimum_total_coverage": MIN_TOTAL_COVERAGE,
        "target_total_coverage": TARGET_TOTAL_COVERAGE,
        "targets": list(COVERAGE_TARGETS),
        "shards": [item.name for item in COVERAGE_SHARDS],
        "completed_shards": completed_shards,
        "json_artifact": str(paths["json"].relative_to(repo_root())),
        "xml_artifact": str(paths["xml"].relative_to(repo_root())),
        "html_artifact": str(paths["html"].relative_to(repo_root())),
        "violations": violations,
        "warnings": warnings,
        "claims_code_coverage": True,
        "claims_target_coverage_reached": percent >= TARGET_TOTAL_COVERAGE,
        "claims_production_ready": False,
    }
    _write_summary(payload)
    if payload["status"] != "ready":
        return False, f"coverage.py gate failed: percent={percent:.2f} minimum={MIN_TOTAL_COVERAGE:.2f} target={TARGET_TOTAL_COVERAGE:.2f} violations={violations} warnings={warnings}"
    suffix = f" warnings={warnings}" if warnings else ""
    return True, f"coverage.py gate passed: percent={percent:.2f} minimum={MIN_TOTAL_COVERAGE:.2f} target={TARGET_TOTAL_COVERAGE:.2f}{suffix}"


__all__ = ["run"]
