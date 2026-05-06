from __future__ import annotations
from tests.arch._canon_arch_audit_index import absolute_path

REQUIRED_NEW_FILES = (
    "docs/CANON_DOMAIN_REGISTRY_AUDIT_V1.md",
    "docs/CANON_DOMAIN_REGISTRY_REMEDIATION_V1.md",
    "tests/arch/_canon_domain_registry_guard.py",
    "tests/arch/test_domain_registry_canonical_domains_have_required_core_files.py",
    "tests/arch/test_domain_registry_canonical_domains_are_not_empty.py",
)

def test_arch_audit_index_tracks_domain_registry_pack() -> None:
    missing = [rel for rel in REQUIRED_NEW_FILES if not absolute_path(rel).exists()]
    assert not missing, "Domain registry audit pack is incomplete. Missing:\n- " + "\n- ".join(missing)
