from __future__ import annotations

import os
from pathlib import Path

import pytest

import scripts.ados_shadow_assess as shadow


def _valid_payload() -> dict:
    return {
        "task": {"risk": "HIGH"},
        "results": [{"gate": "supply_chain", "status": "FAIL", "reason": "example"}],
        "blocking_failures": 1,
        "unknown_gates": 0,
        "release_blockers": 1,
    }


def test_valid_advisory_block_payload_accepts_nonzero_ados_exit() -> None:
    payload = _valid_payload()
    assert shadow.validate_assessment_payload(payload, returncode=2) is payload


def test_error_payload_is_infrastructure_failure() -> None:
    with pytest.raises(RuntimeError, match="controller error"):
        shadow.validate_assessment_payload({"error": "failed to prepare assessment"}, returncode=2)


def test_missing_assessment_fields_are_rejected() -> None:
    with pytest.raises(RuntimeError, match="release_blockers"):
        shadow.validate_assessment_payload({"task": {}, "results": [], "blocking_failures": 0, "unknown_gates": 0}, returncode=0)


def test_lockfile_compatibility_is_same_inode_and_cleanup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    canonical = tmp_path / "requirements.lock.txt"
    alias = tmp_path / "requirements.lock"
    canonical.write_bytes(b"locked-dependencies\n")
    monkeypatch.setattr(shadow, "CANONICAL_PYTHON_LOCK", canonical)
    monkeypatch.setattr(shadow, "ADOS_PYTHON_LOCK_ALIAS", alias)
    with shadow.ados_lockfile_compatibility():
        assert alias.exists()
        assert os.path.samefile(canonical, alias)
        assert alias.read_bytes() == canonical.read_bytes()
    assert not alias.exists()


def test_lockfile_compatibility_refuses_preexisting_alias(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    canonical = tmp_path / "requirements.lock.txt"
    alias = tmp_path / "requirements.lock"
    canonical.write_text("canonical\n")
    alias.write_text("other\n")
    monkeypatch.setattr(shadow, "CANONICAL_PYTHON_LOCK", canonical)
    monkeypatch.setattr(shadow, "ADOS_PYTHON_LOCK_ALIAS", alias)
    with pytest.raises(RuntimeError, match="already exists"):
        with shadow.ados_lockfile_compatibility():
            pass
    assert alias.read_text() == "other\n"
