from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MATRIX_WORKFLOWS = (
    ".github/workflows/ci-doctor.yml",
    ".github/workflows/ci-fast.yml",
    ".github/workflows/targeted-domain-ci.yml",
)
SPLIT_VERSION_WORKFLOWS = (
    ".github/workflows/ci-full.yml",
    ".github/workflows/ci.yml",
)


def test_matrix_versions_are_present_in_workflows() -> None:
    offenders: list[str] = []
    for rel in (*MATRIX_WORKFLOWS, *SPLIT_VERSION_WORKFLOWS):
        path = ROOT / rel
        if not path.is_file():
            offenders.append(f"{rel}:missing")
            continue
        text = path.read_text(encoding="utf-8")
        if '"3.11"' not in text or '"3.12"' not in text:
            offenders.append(rel)
    assert not offenders, f"workflow Python 3.11/3.12 coverage missing: {offenders}"
