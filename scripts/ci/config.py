from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SECURITY_TEST_TARGET = "tests/security"


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
            rel
            for rel in (
                "tests/integration",
                "tests/runtime",
                "tests/interfaces",
            )
            if (root / rel).exists()
        ),
        lock_targets=tuple(
            rel
            for rel in (
                "tests/p0/test_startup_hooks_lightweight.py",
                "tests/p0/test_ci_gate_plan_is_bounded.py",
                "tests/lock/test_no_merge_conflict_markers.py",
                "tests/lock/test_no_patch_artifacts_extended.py",
                "tests/lock/test_no_reject_artifacts.py",
                "tests/lock/test_super_locks_no_zip_sqlite.py",
                "tests/lock/test_super_locks_bytescan.py",
                "tests/lock/test_lock_cicd_contract_files_present.py",
                "tests/lock/test_github_workflow_supply_chain.py",
                "tests/lock/test_deep_release_workflow_contract.py",
                "tests/lock/test_runtime_release_package_hygiene.py",
                "tests/lock/test_ai_ceo_no_second_path.py",
                "tests/lock/test_runtime_actions_registry_lock.py",
                "tests/lock/test_messaging_channel_surface_lock.py",
                "tests/lock/test_known_full_suite_debt_registry.py",
                "tests/arch/test_agi_no_second_brain_surfaces.py",
            )
            if (root / rel).exists()
        ),
        unit_targets=tuple(
            rel
            for rel in (
                "tests/unit",
                "tests/core",
                SECURITY_TEST_TARGET,
                "tests/growth",
                "tests/growth_strategy",
                "tests/autopilot",
                "tests/ads",
                "tests/ads_autopilot",
                "tests/core/product",
                "tests/core/experiments",
                "tests/external_integrations",
            )
            if (root / rel).exists()
        )
        or ("tests",),
        quality_targets=tuple(
            rel
            for rel in (
                "application",
                "core",
                "runtime",
                "interfaces",
                "scripts",
                "tests",
                "canon",
                "contracts",
                "config",
                "market_intelligence",
                "integration_observations",
                "crm/__init__.py",
                "crm/providers/salesforce",
                "crm/providers/amocrm",
                "crm/providers/bitrix24",
                "crm/providers/common/crm_oauth_query_client.py",
                "crm/onboarding/crm_connection_flow.py",
                "crm/onboarding/crm_provider_connection_metadata.py",
                "crm/registry/crm_connector_registry.py",
                "crm/registry/crm_provider_catalog.py",
                "crm/registry/crm_provider_definition.py",
                "crm/registry/crm_provider_definitions.py",
                "crm/registry/crm_provider_assembly.py",
                "crm/registry/crm_registry_consistency.py",
                "crm/state/crm_state_feed.py",
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
            ".github/workflows/deep-release-validation.yml",
            ".github/workflows/docker-image.yml",
            ".github/workflows/full-ci.yml",
            ".github/workflows/prune-stale-branches.yml",
            ".github/workflows/targeted-domain-ci.yml",
            ".github/workflows/trusted-production-certification.yml",
        ),
        matrix_python_versions=("3.11", "3.12"),
    )
