from __future__ import annotations

from pathlib import Path

PAGE_MODULES = [
    Path('app/web/pages/admin.py'),
    Path('app/web/pages/approvals.py'),
    Path('app/web/pages/audit.py'),
    Path('app/web/pages/policy_overrides.py'),
    Path('app/web/pages/queue_history.py'),
    Path('app/web/pages/queue_ops.py'),
    Path('app/web/pages/runtime_alerts.py'),
    Path('app/web/pages/security.py'),
    Path('app/web/pages/tenants.py'),
]


def test_page_modules_import_components_via_public_api_only() -> None:
    for path in PAGE_MODULES:
        text = path.read_text(encoding='utf-8')
        assert 'from app.web.components import ' in text, path
        assert 'from app.web.components.' not in text, path
