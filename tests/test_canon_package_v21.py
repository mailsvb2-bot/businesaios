from __future__ import annotations

import os
from pathlib import Path

from canon import (
    CANON_RULES,
    CANON_VERSION,
    CRITICAL_ERROR_TYPES,
    REPORT_REQUIREMENTS,
    WORK_PROTOCOL,
    WORLD_MODEL_CANON_VERSION,
    REQUIRED_WORLD_MODEL_CANON_FILES,
    required_first_pass,
    required_second_pass,
    run_architecture_checks,
    scan_repo,
    scan_world_model_canon_contract,
    verify_canon_loaded,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_canon_rules_loaded() -> None:
    assert CANON_VERSION == 'V21'
    assert WORLD_MODEL_CANON_VERSION == 'WM-CONTRACT-V1'
    assert CANON_RULES['mandatory_reading'] is True
    assert CANON_RULES['world_model_single_canonical_path'] is True
    assert verify_canon_loaded() is True


def test_canon_protocol_and_report_requirements_are_complete() -> None:
    assert 'Read the canonical source of truth: docs/SYSTEM_TZ_CANONICAL.md' in WORK_PROTOCOL
    assert 'Verify one canonical world-model path into DecisionCore' in WORK_PROTOCOL
    assert 'Write full technical report' in WORK_PROTOCOL
    assert required_first_pass() == 10
    assert required_second_pass() == 15
    assert 'second brain' in CRITICAL_ERROR_TYPES
    assert 'world-model pinning verification' in REPORT_REQUIREMENTS
    assert 'bootstrap/world_model_contract.py' in REQUIRED_WORLD_MODEL_CANON_FILES


def test_architecture_guard_passes_from_repo_root() -> None:
    current = Path.cwd()
    try:
        os.chdir(REPO_ROOT)
        assert run_architecture_checks() is True
    finally:
        os.chdir(current)


def test_repo_cleaner_finds_no_junk_in_fresh_tree() -> None:
    junk = scan_repo(str(REPO_ROOT))
    assert not junk


def test_world_model_super_canon_contract_passes() -> None:
    findings = scan_world_model_canon_contract(REPO_ROOT)
    assert findings == []