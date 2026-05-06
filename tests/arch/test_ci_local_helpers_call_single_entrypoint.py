from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FILES = [
    ".githooks/pre-push",
    "scripts/dev/pre_release_gate.py",
]


def test_local_helpers_use_single_entrypoint() -> None:
    offenders: list[str] = []
    for rel in FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if "scripts/ci/cli.py" not in text:
            offenders.append(rel)
    assert not offenders, f"local helper does not use canonical entrypoint: {offenders}"
