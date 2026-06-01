from __future__ import annotations

from tests.arch._canon_exception_registry_guard import REGISTRY_PATH


def test_exception_registry_file_present() -> None:
    assert REGISTRY_PATH.exists(), "Canonical exception registry file is missing: docs/CANON_EXCEPTION_REGISTRY_DATA_V1.yaml"
