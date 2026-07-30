from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LOCKED_WORKFLOWS = {
    ".github/workflows/ci-doctor.yml": "requirements.lock.txt",
    ".github/workflows/ci-fast.yml": "requirements.lock.txt",
    ".github/workflows/ci-full.yml": "requirements.lock.txt",
    ".github/workflows/ci.yml": "requirements.lock.txt",
    ".github/workflows/full-ci.yml": "requirements.lock.txt",
    ".github/workflows/targeted-domain-ci.yml": "requirements.lock.txt",
    ".github/workflows/deep-release-validation.yml": "requirements.release.lock.txt",
}


def test_workflows_use_cache_dependency_path() -> None:
    offenders: list[str] = []
    for rel, lock_name in LOCKED_WORKFLOWS.items():
        path = ROOT / rel
        if not path.is_file():
            offenders.append(f"{rel}:missing")
            continue
        text = path.read_text(encoding="utf-8")
        if lock_name not in text or "requirements.optional.txt" in text:
            offenders.append(rel)
    assert not offenders, f"workflow dependency lock hardening missing: {offenders}"
