from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _production_owners(symbol: str) -> list[str]:
    pattern = re.compile(rf"^class\s+{re.escape(symbol)}\b", re.MULTILINE)
    owners: list[str] = []
    for path in ROOT.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith((".git/", ".venv/", "venv/", "tests/")):
            continue
        if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
            owners.append(relative)
    return sorted(owners)


def test_phase14_evaluation_and_calibration_have_single_canonical_owner() -> None:
    expected = ["application/outcome/evaluation.py"]
    assert _production_owners("EvaluationEngine") == expected
    assert _production_owners("CalibrationEngine") == expected


def test_phase14_reuses_existing_evidence_store_without_parallel_persistence() -> None:
    persistence = (
        ROOT / "application/evidence/evidence_persistence.py"
    ).read_text(encoding="utf-8")
    projection = (
        ROOT / "application/outcome/evidence_projection.py"
    ).read_text(encoding="utf-8")

    assert '"evaluation": evaluation' in persistence
    assert '"calibration_observation": calibration_observation' in persistence
    assert "class BusinessOutcomeEvaluationProjector:" in projection
    assert "BusinessOutcomeEvidenceProjector(evidence_store)" in projection
