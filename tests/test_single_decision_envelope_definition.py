import re
from pathlib import Path


def test_single_decision_envelope_definition():
    """There must be exactly one DecisionEnvelope class definition."""

    root = Path(__file__).resolve().parents[1]
    canonical = Path("contracts/decisioning/sovereign_decision_contract.py")
    hits = []
    pat = re.compile(r"^\s*class\s+DecisionEnvelope\s*(\(|:)\s*", re.MULTILINE)
    for path in root.rglob("*.py"):
        if path.name == "test_single_decision_envelope_definition.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if pat.search(text):
            hits.append(path.relative_to(root))

    assert hits == [canonical], f"DecisionEnvelope definitions found: {hits}"
