from __future__ import annotations

from app.web.routes import Routes


def test_unknown_pages_are_filtered_from_route_table() -> None:
    routes = Routes()
    built = routes.build(
        {
            'tenant_id': 'tenant-a',
            'routes': (
                {'path': '/web/admin', 'page': 'AdminPage', 'tenant_required': True},
                {'path': '/web/broken', 'page': 'DefinitelyNotAPage', 'tenant_required': False},
            ),
        }
    )
    rows = built['payload']['routes']
    assert len(rows) == 1
    assert rows[0]['page'] == 'AdminPage'
