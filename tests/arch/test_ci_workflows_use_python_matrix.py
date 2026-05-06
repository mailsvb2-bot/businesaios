from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


WORKFLOWS = [
    ".github/workflows/ci-doctor.yml",
    ".github/workflows/ci-fast.yml",
    ".github/workflows/ci-full.yml",
    ".github/workflows/release.yml",
]


def test_matrix_versions_are_present_in_workflows() -> None:
    offenders: list[str] = []
    for rel in WORKFLOWS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if '"3.11"' not in text or '"3.12"' not in text:
            offenders.append(rel)
    assert not offenders, f"workflow matrix versions missing: {offenders}"
