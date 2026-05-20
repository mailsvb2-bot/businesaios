from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectShapeConfig:
    required_paths: tuple[str, ...]
    optional_integration_targets: tuple[str, ...]
    lock_targets: tuple[str, ...]
    unit_targets: tuple[str, ...]
    quality_targets: tuple[str, ...]
    unit_mark_expression: str
    integration_mark_expression: str
    lock_mark_expression: str
    allowed_ci_shell_files: tuple[str, ...]
    allowed_workflows: tuple[str, ...]
    matrix_python_versions: tuple[str, ...]


def project_shape_config(root: Path) -> ProjectShapeConfig:
    return ProjectShapeConfig(
        required_paths=(
            "Makefile",
            "pytest.ini",
            "requirements.txt",
            "requirements.lock.txt",
            "ruff.toml",
            "pyproject.toml",
            "scripts",
            "tests",
            "runtime",
            "interfaces",
            "ci/check_prod_strict.sh",
            "ci/check_locks.sh",
        ),
        optional_integration_targets=tuple(
            rel for rel in (
                "tests/integration",
                "tests/runtime",
                "tests/interfaces",
            )
            if (root / rel).exists()
        ),
        lock_targets=tuple(
            rel for rel in (
                "tests/p0/test_startup_hooks_lightweight.py",
                "tests/p0/test_ci_gate_plan_is_bounded.py",
                "tests/lock/test_no_merge_conflict_markers.py",
                "tests/lock/test_no_patch_artifacts_extended.py",
                "tests/lock/test_no_reject_artifacts.py",
                "tests/lock/test_super_locks_no_zip_sqlite.py",
                "tests/lock/test_super_locks_bytescan.py",
                "tests/lock/test_lock_cicd_contract_files_present.py",
                "tests/lock/test_ai_ceo_no_second_path.py",
                "tests/lock/test_runtime_actions_registry_lock.py",
                "tests/arch/test_agi_no_second_brain_surfaces.py",
            )
            if (root / rel).exists()
        ),
        unit_targets=tuple(
            rel for rel in (
                "tests/unit",
                "tests/core",
                "tests/security",
                "tests/growth",
                "tests/growth_strategy",
                "tests/autopilot",
                "tests/ads",
                "tests/ads_autopilot",
                "tests/core/product",
                "tests/core/experiments",
            )
            if (root / rel).exists()
        ) or ("tests",),
        quality_targets=tuple(
            rel for rel in (
                "application",
                "core",
                "runtime",
                "interfaces",
                "scripts",
                "tests",
                "canon",
                "contracts",
                "config",
            )
            if (root / rel).exists()
        ),
        unit_mark_expression="not slow and not integration and not gate",
        integration_mark_expression="not slow and not gate",
        lock_mark_expression="not slow",
        allowed_ci_shell_files=(
            "ci/check_prod_strict.sh",
            "ci/check_locks.sh",
            "ci/tlc/run_tlc.sh",
            ".githooks/pre-push",
        ),
        allowed_workflows=(
            ".github/workflows/ci-doctor.yml",
            ".github/workflows/ci-fast.yml",
            ".github/workflows/ci-full.yml",
            ".github/workflows/ci.yml",
            ".github/workflows/docker-image.yml",
            ".github/workflows/full-ci.yml",
            ".github/workflows/release-gates.yml",
            ".github/workflows/release.yml",
        ),
        matrix_python_versions=("3.11", "3.12"),
    )