from boot.platform_boot_contract import build_validated_platform_boot_surface, validate_platform_boot_surface


def test_platform_boot_integrity_report_is_valid() -> None:
    surface = build_validated_platform_boot_surface()
    report = validate_platform_boot_surface(surface)
    assert report.is_valid is True
    snapshot = report.snapshot()
    assert snapshot['config_shared'] is True
    assert snapshot['action_audit_shared'] is True
    assert snapshot['decision_audit_shared'] is True
    assert snapshot['export_service_shared'] is True
    assert snapshot['tenant_metrics_shared'] is True


def test_platform_boot_integrity_includes_shared_telemetry_event_store() -> None:
    surface = build_validated_platform_boot_surface()
    report = validate_platform_boot_surface(surface)
    assert report.telemetry_event_store_shared is True
    assert report.is_valid is True


def test_platform_boot_integrity_includes_shared_security_owner_bundle() -> None:
    surface = build_validated_platform_boot_surface()
    report = validate_platform_boot_surface(surface)
    assert report.api_security_owner_bundle_shared is True
    assert report.is_valid is True
