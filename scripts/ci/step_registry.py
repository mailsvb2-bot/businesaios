from __future__ import annotations

from typing import Callable

from scripts.ci import step_ids as _step_ids
from scripts.ci.config import project_shape_config
from scripts.ci.doctor import run_doctor
from scripts.ci.paths import repo_root
from scripts.ci.pytest_tools import run_pytest_with_report
from scripts.ci.step_build_artifact import run as run_build_artifact
from scripts.ci.step_quality import run as run_quality
from scripts.ci.step_verify_release import run as run_verify_release
from scripts.ci.subprocess_io import run_command, run_python

StepHandler = Callable[[], tuple[bool, str]]


def project_shape() -> str: return _step_ids.project_shape()
def dependency_lock() -> str: return _step_ids.dependency_lock()
def doctor() -> str: return _step_ids.doctor()
def import_smoke() -> str: return _step_ids.import_smoke()
def demo_e2e_smoke() -> str: return _step_ids.demo_e2e_smoke()
def quality() -> str: return _step_ids.quality()
def canon_audit() -> str: return _step_ids.canon_audit()
def lock_tests() -> str: return _step_ids.lock_tests()
def unit_tests() -> str: return _step_ids.unit_tests()
def integration_tests() -> str: return _step_ids.integration_tests()
def verify_release() -> str: return _step_ids.verify_release()
def build_artifact() -> str: return _step_ids.build_artifact()


def run_dependency_lock() -> tuple[bool, str]:
    outcome = run_python(["scripts/ci/check_requirements_lock.py"], timeout=30)
    if outcome.returncode != 0:
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "dependency lock drift detected"
    return True, outcome.stdout.strip() or "dependency lock passed"


def run_import_smoke() -> tuple[bool, str]:
    outcome = run_python(["scripts/import_smoke.py"], timeout=90)
    if outcome.returncode != 0:
        return False, "import smoke failed or timed out"
    return True, "import smoke passed"


def run_demo_e2e_smoke() -> tuple[bool, str]:
    outcome = run_command(
        ["python", "main.py"],
        env={
            "RUN_MODE": "demo",
            "DEMO_E2E_SMOKE": "1",
            "APP_ENV": "ci",
            "ENV": "ci",
            "TENANT_ID": "ci-demo-tenant",
            "SYSTEM_TZ": "Europe/Amsterdam",
            "CI_STEP_TIMEOUT_SECONDS": "180",
        },
        timeout=180,
    )
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, "demo e2e smoke timed out"
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "demo e2e smoke failed"
    return True, "demo e2e smoke passed"


def run_canon_audit() -> tuple[bool, str]:
    code = (
        "from pathlib import Path; "
        "from tools.canon_audit import run_operational_canon_checks; "
        "r=run_operational_canon_checks(Path.cwd()); "
        "print(f'passed={r.passed} score={r.admission_score_100} violations={len(r.violations)}'); "
        "raise SystemExit(0 if r.passed else 1)"
    )
    outcome = run_python(["-c", code], timeout=180)
    if outcome.returncode != 0:
        if outcome.returncode == 124:
            return False, "operational canon timed out"
        return False, "operational canon failed"
    return True, "operational canon passed"


def run_project_shape() -> tuple[bool, str]:
    root = repo_root()
    cfg = project_shape_config(root)
    missing = [rel for rel in cfg.required_paths if not (root / rel).exists()]
    if missing:
        return False, f"missing required paths: {missing}"
    return True, "project shape contract satisfied"


def _repo_hygiene_files(root):
    skip_dirs = {
        ".git", ".artifacts", "artifacts", ".venv", "venv", "__pycache__",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", "dist",
    }
    for path in root.rglob("*"):
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.is_file():
            yield path


def _bounded_text_files(root):
    text_names = {"Dockerfile", "Makefile", ".gitignore"}
    text_suffixes = {
        ".py", ".md", ".yml", ".yaml", ".toml", ".ini", ".json", ".txt", ".sh", ".env", ".cfg",
    }
    for path in _repo_hygiene_files(root):
        try:
            if path.stat().st_size > 2_000_000:
                continue
        except OSError:
            continue
        if path.name in text_names or path.suffix.lower() in text_suffixes:
            yield path


def _direct_repo_hygiene_lock() -> tuple[bool, str]:
    root = repo_root()
    conflict_hits: list[str] = []
    patch_hits: list[str] = []
    archive_hits: list[str] = []
    for path in _repo_hygiene_files(root):
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        if suffix in {".rej", ".orig", ".bak"}:
            patch_hits.append(rel)
        if suffix in {".zip", ".tar", ".tgz", ".gz", ".7z", ".rar", ".sqlite", ".sqlite3", ".db"}:
            archive_hits.append(rel)

    left_marker = ("<" * 7).encode()
    right_marker = (">" * 7).encode()
    for path in _bounded_text_files(root):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("tests/"):
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if left_marker in data or right_marker in data:
            conflict_hits.append(rel)

    if conflict_hits:
        return False, "merge conflict markers found: " + ", ".join(sorted(conflict_hits)[:20])
    if patch_hits:
        return False, "patch/backup artifacts found: " + ", ".join(sorted(patch_hits)[:20])
    if archive_hits:
        return False, "forbidden archive/db artifacts found: " + ", ".join(sorted(archive_hits)[:20])
    return True, "repo hygiene locks passed"


def _direct_cicd_contract_lock() -> tuple[bool, str]:
    from tests.lock.test_lock_cicd_contract_files_present import REQUIRED
    root = repo_root()
    missing = [rel for rel in REQUIRED if not (root / rel).exists()]
    if missing:
        return False, f"missing ci/cd contract files: {missing}"
    return True, "ci/cd contract lock passed"


def _direct_second_brain_surface_lock() -> tuple[bool, str]:
    from tests.arch.test_agi_no_second_brain_surfaces import FORBIDDEN_SURFACES
    offenders = [rel for rel in FORBIDDEN_SURFACES if (repo_root() / rel).exists()]
    if offenders:
        return False, "forbidden second-brain surfaces exist: " + ", ".join(offenders)
    return True, "second-brain surface lock passed"


def _direct_ai_ceo_lock() -> tuple[bool, str]:
    root = repo_root()
    needle = "ai" + "_ceo" + "_plan" + "@v1"
    allowed_prefixes = tuple(
        str(root / rel) for rel in (
            "core/ai_ceo",
            "core/policies/telegram/handlers/ai_ceo.py",
            "runtime/handlers/ai_ceo_plan.py",
            "runtime/boot/actions_catalog.py",
            "runtime/boot/actions_registry.py",
            "runtime/boot/registration_manifest.py",
        )
    )
    hits: list[str] = []
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "tests" in path.parts or "artifacts" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if needle in text:
            full = str(path)
            hits.append(path.relative_to(root).as_posix())
            if not any(full.startswith(prefix) for prefix in allowed_prefixes):
                offenders.append(path.relative_to(root).as_posix())
    if not hits:
        return False, "expected canonical AI CEO action to be referenced"
    if offenders:
        return False, "unexpected AI CEO second-path references: " + ", ".join(sorted(offenders)[:20])
    return True, "AI CEO single-path lock passed"


def _direct_runtime_actions_registry_lock() -> tuple[bool, str]:
    runtime_import = "from " + "runtime.boot.actions_registry" + " import SPECS, INLINE_ALLOWLIST, all_actions\n"
    manifest_import = "from " + "runtime.boot.registration_manifest" + " import registered_action_names\n"
    code = (
        "import os\n"
        "import re\n"
        "from pathlib import Path\n"
        + runtime_import
        + manifest_import
        + r'''
root = Path.cwd()
expected = all_actions()
registered = set(registered_action_names())
if registered != expected:
    print(f"runtime registry drift: missing={sorted(expected-registered)} extra={sorted(registered-expected)}")
    os._exit(1)

offenders = []
for path in (root / "runtime").rglob("*.py"):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        continue
    for action in re.findall(r'handlers\.register\(\s*"([^"]+)"', text):
        if action not in expected:
            offenders.append(f"{path.relative_to(root).as_posix()}:{action}")
if offenders:
    print("unregistered runtime-actions found: " + ", ".join(sorted(offenders)[:20]))
    os._exit(1)

read_only = {"noop@v1", "poll_telegram_updates@v1", "telegram_self_check@v1"}
for name, spec in SPECS.items():
    if spec.name != name:
        print(f"runtime action spec name mismatch for {name}")
        os._exit(1)
    if spec.limits is None:
        print(f"runtime action lacks limits: {name}")
        os._exit(1)
    if name == "noop@v1":
        if spec.limits.kind != "none":
            print("noop@v1 must have none limits")
            os._exit(1)
    elif spec.limits.kind == "none" or spec.limits.per_tenant_per_min <= 0 or spec.limits.per_user_per_min <= 0:
        print(f"runtime action invalid limits: {name}")
        os._exit(1)
    if not spec.handler_ref or not isinstance(spec.handler_ref, str):
        print(f"runtime action missing handler_ref: {name}")
        os._exit(1)
    if name not in INLINE_ALLOWLIST and not spec.handler_ref.startswith(("runtime.handlers.", "runtime.handlers_")):
        print(f"runtime action invalid handler_ref: {name}:{spec.handler_ref}")
        os._exit(1)
    expected_idempotency = name not in read_only
    if spec.requires_idempotency_key is not expected_idempotency:
        print(f"runtime action idempotency mismatch: {name}")
        os._exit(1)
print("runtime actions registry lock passed")
os._exit(0)
'''
    )
    outcome = run_python(["-c", code], timeout=90)
    if outcome.returncode != 0:
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "runtime actions registry lock failed"
    return True, "runtime actions registry lock passed"


def run_lock_tests() -> tuple[bool, str]:
    checks = (
        _direct_repo_hygiene_lock,
        _direct_cicd_contract_lock,
        _direct_second_brain_surface_lock,
        _direct_ai_ceo_lock,
        _direct_runtime_actions_registry_lock,
    )
    messages: list[str] = []
    for check in checks:
        ok, message = check()
        if not ok:
            return False, message
        messages.append(message)
    return True, "; ".join(messages)


def run_unit_tests() -> tuple[bool, str]:
    cfg = project_shape_config(repo_root())
    targets = list(cfg.unit_targets)
    if not targets:
        return False, "unit target set is empty"
    ok, message = run_pytest_with_report(
        target_args=targets,
        mark_expression=cfg.unit_mark_expression,
        junit_name="unit.xml",
        coverage_name="unit-coverage.xml",
        timeout=240,
    )
    if not ok:
        return False, message
    return True, "unit test gate passed"


def run_integration_tests() -> tuple[bool, str]:
    cfg = project_shape_config(repo_root())
    targets = list(cfg.optional_integration_targets)
    if not targets:
        return True, "integration targets absent; skipped by contract"
    ok, message = run_pytest_with_report(
        target_args=targets,
        mark_expression=cfg.integration_mark_expression,
        junit_name="integration.xml",
        coverage_name="integration-coverage.xml",
        timeout=240,
    )
    if not ok:
        return False, message
    return True, "integration test gate passed"


_REGISTRY: dict[str, StepHandler] = {
    project_shape(): run_project_shape,
    dependency_lock(): run_dependency_lock,
    doctor(): run_doctor,
    import_smoke(): run_import_smoke,
    demo_e2e_smoke(): run_demo_e2e_smoke,
    quality(): run_quality,
    canon_audit(): run_canon_audit,
    lock_tests(): run_lock_tests,
    unit_tests(): run_unit_tests,
    integration_tests(): run_integration_tests,
    verify_release(): run_verify_release,
    build_artifact(): run_build_artifact,
}


def handler_for_step(name: str) -> StepHandler:
    if name not in _REGISTRY:
        raise KeyError(f"unknown step: {name}")
    return _REGISTRY[name]
