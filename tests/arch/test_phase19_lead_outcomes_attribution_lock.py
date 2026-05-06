from __future__ import annotations

import re
from pathlib import Path

import attribution
import lead_outcomes

ROOT = Path(__file__).resolve().parents[2]
ATTRIBUTION_IMPORT = re.compile(r"^\s*(?:from\s+attribution\b|import\s+attribution\b)", re.MULTILINE)
LEAD_OUTCOMES_IMPORT = re.compile(r"^\s*(?:from\s+lead_outcomes\b|import\s+lead_outcomes\b)", re.MULTILINE)
BASEREGISTRY_IMPORT = re.compile(r"^\s*(?:from\s+registry\.base_registry\b|import\s+registry\.base_registry\b)", re.MULTILINE)
REQUIRED_EXPORTS = (
    "LeadStatusTracker",
    "LeadResponseTracker",
    "LeadRevenueTracker",
)

def _python_files_under(rel_dir: str) -> list[Path]:
    base = ROOT / rel_dir
    return sorted(path for path in base.rglob("*.py") if path.is_file())

def test_lead_outcomes_and_attribution_roles_and_boundaries_stay_distinct() -> None:
    lo_role = (ROOT / "lead_outcomes" / "CANON_NAMESPACE_ROLE.md").read_text(encoding="utf-8")
    assert "canonical mutable lead-outcome state surface" in lo_role
    assert "second attribution provenance truth" in lo_role

    attr_role = (ROOT / "attribution" / "CANON_NAMESPACE_ROLE.md").read_text(encoding="utf-8")
    assert "canonical attribution and provenance surface" in attr_role
    assert "second mutable lead outcome registry" in attr_role

    assert lead_outcomes.CANON_LEAD_OUTCOME_STATE_NAMESPACE is True
    assert attribution.CANON_ATTRIBUTION_PROVENANCE_NAMESPACE is True

    offenders = []
    for path in _python_files_under("lead_outcomes"):
        text = path.read_text(encoding="utf-8")
        if ATTRIBUTION_IMPORT.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], offenders

    offenders = []
    for path in _python_files_under("attribution"):
        text = path.read_text(encoding="utf-8")
        if LEAD_OUTCOMES_IMPORT.search(text):
            offenders.append(str(path.relative_to(ROOT)))
        if BASEREGISTRY_IMPORT.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], offenders

    exports = (ROOT / "lead_outcomes" / "__init__.py").read_text(encoding="utf-8")
    for name in REQUIRED_EXPORTS:
        assert name in exports
