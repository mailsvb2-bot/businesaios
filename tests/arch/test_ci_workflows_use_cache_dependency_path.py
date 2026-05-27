from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


WORKFLOWS = [
    ".github/workflows/ci-doctor.yml",
    ".github/workflows/ci-fast.yml",
    ".github/workflows/ci-full.yml",
    ".github/workflows/release.yml",
]


def test_workflows_use_cache_dependency_path() -> None:
    offenders: list[str] = []
    for rel in WORKFLOWS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        required = [
            'cache-dependency-path:',
            'requirements.txt',
            'requirements.optional.txt',
            'requirements.lock.txt',
        ]
        if not all(item in text for item in required):
            offenders.append(rel)
    assert not offenders, f"workflow cache hardening missing: {offenders}"
