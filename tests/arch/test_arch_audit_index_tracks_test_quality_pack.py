from __future__ import annotations
from tests.arch._canon_arch_audit_index import absolute_path

REQUIRED_NEW_FILES = (
    "docs/CANON_TEST_QUALITY_AUDIT_V1.md",
    "docs/CANON_TEST_QUALITY_REMEDIATION_V1.md",
    "tests/arch/_canon_test_quality_guard.py",
    "tests/arch/test_test_quality_arch_tests_have_real_asserts.py",
    "tests/arch/test_test_quality_no_placeholder_or_decorative_markers.py",
    "tests/arch/test_test_quality_arch_tests_not_suspiciously_short.py",
    "tests/arch/test_test_quality_arch_tests_have_real_test_functions.py",
    "tests/arch/test_test_quality_arch_tests_have_quality_signals.py",
    "tests/arch/test_test_quality_no_import_only_pseudo_tests.py",
)

def test_arch_audit_index_tracks_test_quality_pack() -> None:
    missing = [rel for rel in REQUIRED_NEW_FILES if not absolute_path(rel).exists()]
    assert not missing, "Test quality audit pack is incomplete. Missing:\n- " + "\n- ".join(missing)
