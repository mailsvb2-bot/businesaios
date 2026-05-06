from boot.platform_boot_contract import build_validated_platform_boot_surface, validate_platform_boot_surface


def test_platform_boot_integrity_includes_shared_telemetry_event_store() -> None:
    surface = build_validated_platform_boot_surface()
    report = validate_platform_boot_surface(surface)
    assert report.telemetry_event_store_shared is True
    assert report.is_valid is True
