from __future__ import annotations

from pathlib import Path

import pytest

from application.analytics.analytics_export_path_policy import AnalyticsExportPathPolicy
from application.analytics.analytics_export_service import AnalyticsExportService
from application.analytics.analytics_signed_export_service import AnalyticsSignedExportService


def test_materialized_export_stays_inside_server_root(tmp_path) -> None:
    root = tmp_path / 'exports'
    service = AnalyticsExportService(export_root=root)
    exported = Path(
        service.export_bundle(
            export_path='daily/dashboard.json',
            bundle={'ok': True},
            tenant_id='tenant-a',
        )
    )
    relative = exported.relative_to(root.resolve())
    assert relative.parts[0].startswith('tenant-')
    assert relative.parts[1:] == ('daily', 'dashboard.json')
    assert exported.is_file()

    for malicious in ('../pwned.json', '/tmp/pwned.json', 'C:/pwned.json'):
        with pytest.raises(ValueError):
            service.export_bundle(export_path=malicious, bundle={}, tenant_id='tenant-a')


def test_custom_export_paths_are_isolated_between_tenants(tmp_path) -> None:
    root = tmp_path / 'exports'
    service = AnalyticsExportService(export_root=root)

    tenant_a = Path(
        service.export_bundle(
            export_path='daily/dashboard.json',
            bundle={'tenant': 'a'},
            tenant_id='tenant-a',
        )
    )
    tenant_b = Path(
        service.export_bundle(
            export_path='daily/dashboard.json',
            bundle={'tenant': 'b'},
            tenant_id='tenant-b',
        )
    )

    assert tenant_a != tenant_b
    assert tenant_a.relative_to(root.resolve()).parts[0] != tenant_b.relative_to(root.resolve()).parts[0]
    assert tenant_a.read_text(encoding='utf-8') != tenant_b.read_text(encoding='utf-8')


def test_signed_export_rejects_traversal_in_directory_and_export_id(tmp_path) -> None:
    root = tmp_path / 'exports'
    service = AnalyticsSignedExportService(export_root=root)

    for malicious_id in ('../pwned', 'x/../../pwned', '..'):
        with pytest.raises(ValueError, match='invalid_export_id'):
            service.export_signed_bundle(
                export_dir='daily',
                export_id=malicious_id,
                tenant_id='tenant-a',
                bundle={},
            )

    for malicious_dir in ('../outside', '/tmp/outside'):
        with pytest.raises(ValueError):
            service.export_signed_bundle(
                export_dir=malicious_dir,
                export_id='safe-id',
                tenant_id='tenant-a',
                bundle={},
            )


def test_signed_export_directories_are_isolated_between_tenants(tmp_path) -> None:
    root = tmp_path / 'exports'
    service = AnalyticsSignedExportService(export_root=root)

    tenant_a = service.export_signed_bundle(
        export_dir='daily',
        export_id='snapshot',
        tenant_id='tenant-a',
        bundle={'tenant': 'a'},
    )
    tenant_b = service.export_signed_bundle(
        export_dir='daily',
        export_id='snapshot',
        tenant_id='tenant-b',
        bundle={'tenant': 'b'},
    )

    tenant_a_bundle = Path(tenant_a['bundle_file'])
    tenant_b_bundle = Path(tenant_b['bundle_file'])
    assert tenant_a_bundle != tenant_b_bundle
    assert tenant_a_bundle.parent.parent != tenant_b_bundle.parent.parent


def test_symlink_escape_is_rejected(tmp_path) -> None:
    root = tmp_path / 'exports'
    outside = tmp_path / 'outside'
    outside.mkdir()
    policy = AnalyticsExportPathPolicy(export_root=root)
    tenant_root = policy.resolve_directory(requested_dir=None, tenant_id='tenant-a')
    tenant_root.mkdir(parents=True)
    link = tenant_root / 'escape'
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('symlinks are unavailable on this platform')

    service = AnalyticsExportService(export_root=root)
    with pytest.raises(ValueError, match='outside_sandbox'):
        service.export_bundle(
            export_path='escape/pwned.json',
            bundle={},
            tenant_id='tenant-a',
        )
