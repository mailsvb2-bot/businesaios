from pathlib import Path
import re


def test_single_decision_envelope_definition():
    """There must be exactly one DecisionEnvelope class definition.

    Rationale: parallel envelope models create a second execution/verification contour.
    """

    root = Path(__file__).resolve().parents[1]
    hits = []
    pat = re.compile(r"^\s*class\s+DecisionEnvelope\s*(\(|:)\s*", re.MULTILINE)
    for p in root.rglob("*.py"):
        if p.name == "test_single_decision_envelope_definition.py":
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if pat.search(txt):
            if p.as_posix().endswith("core/ai/decision.py"):
                continue
            hits.append(str(p.relative_to(root)))

    assert hits == [], f"Non-canonical DecisionEnvelope definitions found: {hits}"
