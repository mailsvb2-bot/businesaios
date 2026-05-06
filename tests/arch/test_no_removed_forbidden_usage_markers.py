from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_repository_contains_no_removed_forbidden_usage_markers() -> None:
    offenders: list[str] = []
    for path in ROOT.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        if 'REMOVED' + ' forbidden usage' in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == [], offenders
