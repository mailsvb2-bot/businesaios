from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


WORKFLOWS = [
    ".github/workflows/ci-doctor.yml",
    ".github/workflows/ci-fast.yml",
    ".github/workflows/ci-full.yml",
    ".github/workflows/release.yml",
]


def test_workflows_use_single_cli_entrypoint() -> None:
    offenders: list[str] = []

    for rel in WORKFLOWS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "python scripts/ci/cli.py --gate" not in text:
            offenders.append(rel)

    assert not offenders, f"workflow does not use canonical entrypoint: {offenders}"
