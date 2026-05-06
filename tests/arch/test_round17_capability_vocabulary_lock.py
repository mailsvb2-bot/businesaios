from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_capability_vocabulary_names_are_advisory_friendly() -> None:
    path = ROOT / "core" / "decisioning" / "capability_vocabulary.py"
    text = path.read_text(encoding="utf-8")
    assert '"score"' in text
    assert '"observe"' in text
    assert '"validate"' in text
    assert '"recommend"' in text


def test_no_raw_choose_capability_added_to_vocabulary() -> None:
    path = ROOT / "core" / "decisioning" / "capability_vocabulary.py"
    text = path.read_text(encoding="utf-8").lower()
    assert 'capability("choose"' not in text
    assert 'capability("finalize"' not in text
