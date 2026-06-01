from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_PATTERNS = (
    'MonetizationDashboardSnapshot',
    'gross_revenue_minor',
    'net_revenue_minor',
    'active_subscriptions',
)
ALLOWED_OWNERS = (
    'runtime/monetization/',
    'app/web/components/monetization_dashboard_card.py',
    'app/web/pages/admin.py',
    'tests/',
)


def _allowed(path: Path) -> bool:
    normalized = path.as_posix()
    return any(owner in normalized for owner in ALLOWED_OWNERS)


def test_no_shadow_monetization_dashboard_logic_outside_owner() -> None:
    offenders: list[str] = []
    for path in PROJECT_ROOT.rglob('*.py'):
        if _allowed(path):
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            continue
        for pattern in FORBIDDEN_PATTERNS:
            if pattern in text:
                offenders.append(f'{path.as_posix()} :: {pattern}')
    assert not offenders, 'Shadow monetization dashboard logic detected:\n' + '\n'.join(sorted(offenders))
