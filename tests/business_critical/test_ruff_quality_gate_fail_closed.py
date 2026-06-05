from __future__ import annotations

from pathlib import Path


def test_ruff_quality_gate_has_no_legacy_debt_success_state() -> None:
    source = Path("scripts/ci/step_quality.py").read_text(encoding="utf-8")

    assert "ready_with_debt" not in source
    assert "legacy_ruff_debt_present_or_unmeasured" not in source
    assert "full_ruff_strict_not_enforced" not in source
    assert "BAIOS_ALLOW_LEGACY_RUFF_DEBT" not in source


def test_ruff_quality_gate_runs_full_repository_check_by_default() -> None:
    source = Path("scripts/ci/step_quality.py").read_text(encoding="utf-8")

    assert "ruff_fail_closed" in source
    assert "full_repository_quality_targets" in source
    assert "claims_full_ruff_clean" in source
    assert "full_ruff_strict_failed" in source
    assert "BAIOS_REQUIRE_FULL_RUFF" not in source


def test_ruff_quality_gate_emits_honest_artifact() -> None:
    source = Path("scripts/ci/step_quality.py").read_text(encoding="utf-8")

    assert "artifacts" in source
    assert "quality_check.json" in source
    assert '"claims_production_ready": False' in source
    assert '"claims_legacy_ruff_debt_allowed": False' in source
