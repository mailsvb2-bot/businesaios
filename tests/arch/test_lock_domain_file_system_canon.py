from __future__ import annotations

from pathlib import Path

from canon.domain_fs import (
    ALLOWED_SUBDIRS,
    CANON_DOMAIN_MARKER,
    DOMAIN_FILE_SYSTEM_VERSION,
    REQUIRED_ROOT_FILES,
    STRATEGIC_DOMAIN_NAMES,
    scan_canon_domain_file_system,
)

ROOT = Path(__file__).resolve().parents[2]


def test_domain_file_system_canon_constants_are_loaded() -> None:
    assert DOMAIN_FILE_SYSTEM_VERSION == "DFS-V1"
    assert CANON_DOMAIN_MARKER == "__canon_domain__.py"
    assert "world_model" in STRATEGIC_DOMAIN_NAMES
    assert "economics" in STRATEGIC_DOMAIN_NAMES
    assert "simulation" in STRATEGIC_DOMAIN_NAMES
    assert "contracts.py" in REQUIRED_ROOT_FILES
    assert "service.py" in REQUIRED_ROOT_FILES
    assert "guard.py" in REQUIRED_ROOT_FILES
    assert "builders" in ALLOWED_SUBDIRS
    assert "evaluators" in ALLOWED_SUBDIRS
    assert "explainers" in ALLOWED_SUBDIRS


def test_canon_domain_file_system_has_no_findings_in_repo() -> None:
    findings = scan_canon_domain_file_system(ROOT)
    assert findings == [], [f"{i.kind}:{i.path}" for i in findings]
