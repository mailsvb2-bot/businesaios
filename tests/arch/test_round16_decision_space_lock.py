from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_capability_vocabulary_exists():
    path = ROOT / "core" / "decisioning" / "capability_vocabulary.py"
    text = path.read_text(encoding="utf-8")
    assert "Capability(" in text

def test_candidate_space_helper_exists():
    path = ROOT / "core" / "decisioning" / "candidate_space.py"
    text = path.read_text(encoding="utf-8")
    assert "CandidateScore" in text

def test_no_hidden_next_pattern():
    offenders = []
    for p in ROOT.rglob("*.py"):
        if "tests" in str(p):
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if "next((" in txt:
            offenders.append(str(p))
    assert not offenders, f"hidden narrowing pattern found: {offenders}"
