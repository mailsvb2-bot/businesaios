from __future__ import annotations

from pathlib import Path


def test_no_patch_reject_or_backup_files() -> None:
    """Lock-test: no *.rej / *.orig / *.bak should exist in repo.

    These files create "second paths" and are almost always accidental drift.
    """

    repo = Path(__file__).resolve().parents[2]
    bad = []
    for pat in ("*.rej", "*.orig", "*.bak"):
        bad.extend([p for p in repo.rglob(pat) if p.is_file()])

    assert not bad, "Found forbidden drift files:\n" + "\n".join(str(p.relative_to(repo)) for p in bad[:30])
