from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding='utf-8')


def test_core_plans_package_root_is_owner_surface() -> None:
    content = _read('core/plans/__init__.py')
    assert 'CANON_CORE_PLANS_OWNER = True' in content
    for name in ['load_plans', 'active_plans', 'plan_by_id', 'get_plan_by_id']:
        assert name in content


def test_internal_plan_consumers_use_package_root() -> None:
    relpaths = [
        'core/policies/telegram/helpers.py',
        'core/policies/telegram/tariffs.py',
        'core/policies/telegram/handlers/admin/pricing.py',
        'core/policies/telegram/routes/marketing_routes.py',
        'interfaces/telegram/read_models/components/pricing.py',
    ]
    for relpath in relpaths:
        content = _read(relpath)
        assert 'core.plans.catalog' not in content, relpath
        assert 'core.plans' in content, relpath
