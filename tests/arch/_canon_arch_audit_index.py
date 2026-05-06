from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ExpectedPath:
    rel: str
    kind: str


REQUIRED_DOCS: tuple[ExpectedPath, ...] = (
    ExpectedPath("docs/CANON_BOOT_RUNTIME_REGISTRY_AUDIT_V1.md", "doc"),
    ExpectedPath("docs/CANON_BOOT_RUNTIME_REGISTRY_REMEDIATION_V1.md", "doc"),
    ExpectedPath("docs/CANON_DOMAIN_REGISTRY_AUDIT_V1.md", "doc"),
    ExpectedPath("docs/CANON_DOMAIN_REGISTRY_REMEDIATION_V1.md", "doc"),
    ExpectedPath("docs/CANON_TEST_QUALITY_AUDIT_V1.md", "doc"),
    ExpectedPath("docs/CANON_TEST_QUALITY_REMEDIATION_V1.md", "doc"),
    ExpectedPath("docs/CANON_EXCEPTION_REGISTRY_V1.md", "doc"),
    ExpectedPath("docs/CANON_EXCEPTION_REGISTRY_REMEDIATION_V1.md", "doc"),
    ExpectedPath("docs/CANON_MIGRATION_DEPRECATION_REGISTRY_V1.md", "doc"),
    ExpectedPath("docs/CANON_MIGRATION_DEPRECATION_REMEDIATION_V1.md", "doc"),
    ExpectedPath("docs/CANON_META_PACK_INDEX_V1.md", "doc"),
    ExpectedPath("docs/CANON_ONBOARDING_FOR_ARCHITECTS_V1.md", "doc"),
    ExpectedPath("docs/CANON_META_PACK_MANIFEST_V1.yaml", "doc"),
    ExpectedPath("docs/CANON_MASTER_CHECKLIST_V1.md", "doc"),
    ExpectedPath("docs/CANON_MASTER_LAYER_V1.md", "doc"),
)

REQUIRED_HELPERS: tuple[ExpectedPath, ...] = (
    ExpectedPath("tests/arch/_canon_arch_audit_index.py", "helper"),
    ExpectedPath("tests/arch/_canon_boot_runtime_registry_guard.py", "helper"),
    ExpectedPath("tests/arch/_canon_domain_registry_guard.py", "helper"),
    ExpectedPath("tests/arch/_canon_test_quality_guard.py", "helper"),
    ExpectedPath("tests/arch/_canon_exception_registry_guard.py", "helper"),
    ExpectedPath("tests/arch/_canon_migration_registry_guard.py", "helper"),
    ExpectedPath("tests/arch/_canon_meta_pack_guard.py", "helper"),
    ExpectedPath("tests/arch/_canon_master_audit_guard.py", "helper"),
)

REQUIRED_TESTS: tuple[ExpectedPath, ...] = (
    ExpectedPath("tests/arch/test_boot_registry_public_entrypoints_have_markers.py", "test"),
    ExpectedPath("tests/arch/test_boot_registry_public_entrypoints_have_real_entrypoints.py", "test"),
    ExpectedPath("tests/arch/test_handler_registry_public_entrypoints_have_markers.py", "test"),
    ExpectedPath("tests/arch/test_handler_registry_public_entrypoints_have_real_entrypoints.py", "test"),
    ExpectedPath("tests/arch/test_boot_runtime_registry_not_empty.py", "test"),
    ExpectedPath("tests/arch/test_domain_registry_canonical_domains_have_required_core_files.py", "test"),
    ExpectedPath("tests/arch/test_domain_registry_canonical_domains_are_not_empty.py", "test"),
    ExpectedPath("tests/arch/test_test_quality_arch_tests_have_real_asserts.py", "test"),
    ExpectedPath("tests/arch/test_test_quality_no_placeholder_or_decorative_markers.py", "test"),
    ExpectedPath("tests/arch/test_test_quality_arch_tests_not_suspiciously_short.py", "test"),
    ExpectedPath("tests/arch/test_test_quality_arch_tests_have_real_test_functions.py", "test"),
    ExpectedPath("tests/arch/test_test_quality_arch_tests_have_quality_signals.py", "test"),
    ExpectedPath("tests/arch/test_test_quality_no_import_only_pseudo_tests.py", "test"),
)

ALL_EXPECTED: tuple[ExpectedPath, ...] = (*REQUIRED_DOCS, *REQUIRED_HELPERS, *REQUIRED_TESTS)


def absolute_path(rel: str) -> Path:
    return ROOT / rel


def exists(rel: str) -> bool:
    return absolute_path(rel).exists()


def missing(items: tuple[ExpectedPath, ...]) -> list[str]:
    return [item.rel for item in items if not exists(item.rel)]
