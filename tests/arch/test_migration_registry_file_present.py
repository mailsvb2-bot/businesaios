from __future__ import annotations

from tests.arch._canon_migration_registry_guard import REGISTRY_PATH


def test_migration_registry_file_present() -> None:
    assert REGISTRY_PATH.exists(), "Canonical migration/deprecation registry file is missing: docs/CANON_MIGRATION_DEPRECATION_REGISTRY_DATA_V1.yaml"
