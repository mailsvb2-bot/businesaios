from __future__ import annotations

from pathlib import Path

import pytest

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
    assert exported.is_relative_to(root.resolve())
    assert exported.is_file()

    for malicious in ('../pwned.json', '/tmp/pwned.json', 'C:/pwned.json'):
        with pytest.raises(ValueError):
            service.export_bundle(export_path=malicious, bundle={}, tenant_id='tenant-a')


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


def test_symlink_escape_is_rejected(tmp_path) -> None:
    root = tmp_path / 'exports'
    outside = tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    link = root / 'escape'
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
