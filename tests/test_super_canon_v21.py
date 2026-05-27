from __future__ import annotations

import os
from pathlib import Path

from canon import (
    CANON_RULES,
    CANON_VERSION,
    REPORT_REQUIREMENTS,
    REQUIRED_WORLD_MODEL_CANON_FILES,
    WORK_PROTOCOL,
    WORLD_MODEL_CANON_VERSION,
    scan_world_model_canon_contract,
    verify_canon_loaded,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_super_canon_rules_loaded() -> None:
    assert CANON_VERSION == 'V21'
    assert WORLD_MODEL_CANON_VERSION == 'WM-CONTRACT-V1'
    assert CANON_RULES['mandatory_reading'] is True
    assert CANON_RULES['world_model_single_canonical_path'] is True
    assert CANON_RULES['world_model_pinning_required'] is True
    assert verify_canon_loaded() is True


def test_super_canon_protocol_and_reports_are_extended() -> None:
    assert 'Verify one canonical world-model path into DecisionCore' in WORK_PROTOCOL
    assert 'Verify world-model pinning / replay / audit are preserved' in WORK_PROTOCOL
    assert 'world-model canonical path verification' in REPORT_REQUIREMENTS
    assert 'world-model replay and audit verification' in REPORT_REQUIREMENTS


def test_required_world_model_canon_files_declared() -> None:
    assert 'bootstrap/world_model_contract.py' in REQUIRED_WORLD_MODEL_CANON_FILES
    assert 'scripts/check_world_model_integrity.py' in REQUIRED_WORLD_MODEL_CANON_FILES
    assert 'scripts/migrate_world_model_to_canonical.py' in REQUIRED_WORLD_MODEL_CANON_FILES


def test_repo_satisfies_super_canon_contract() -> None:
    current = Path.cwd()
    try:
        os.chdir(REPO_ROOT)
        findings = scan_world_model_canon_contract(REPO_ROOT)
        assert findings == []
    finally:
        os.chdir(current)
