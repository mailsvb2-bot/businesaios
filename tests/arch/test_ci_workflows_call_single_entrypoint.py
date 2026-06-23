from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

WORKFLOWS = [
    '.github/workflows/ci-doctor.yml',
    '.github/workflows/ci-fast.yml',
    '.github/workflows/ci-full.yml',
    '.github/workflows/release.yml',
]

CANONICAL_CLI_ENTRYPOINT = 'python -m scripts.ci.cli --gate'
LEGACY_CLI_FILE_ENTRYPOINT = 'scripts/ci/cli.py'


def test_workflows_use_single_cli_entrypoint() -> None:
    offenders: list[str] = []
    for rel in WORKFLOWS:
        text = (ROOT / rel).read_text(encoding='utf-8')
        if CANONICAL_CLI_ENTRYPOINT not in text or LEGACY_CLI_FILE_ENTRYPOINT in text:
            offenders.append(rel)
    assert not offenders, f'workflow does not use canonical entrypoint: {offenders}'
