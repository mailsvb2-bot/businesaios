from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {
    'advisory/revenue_os',
    'advisory/__init__.py',
    'runtime/monetization/revenue_advisory.py',
    'runtime/monetization/revenue_advisory_contracts.py',
    'tests/',
}


def _allowed(path: Path) -> bool:
    normalized = path.as_posix()
    return any(token in normalized for token in ALLOWED)


def test_no_direct_revenue_os_imports_outside_owner() -> None:
    offenders: list[str] = []
    for path in PROJECT_ROOT.rglob('*.py'):
        if _allowed(path):
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            continue
        if 'advisory.revenue_os' in text:
            offenders.append(path.as_posix())
    assert not offenders, 'Direct advisory.revenue_os imports detected outside owner surfaces:\n' + '\n'.join(sorted(offenders))
