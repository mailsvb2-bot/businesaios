from boot.platform_boot_contract import build_validated_platform_boot_surface, validate_platform_boot_surface


def test_platform_boot_integrity_includes_shared_security_owner_bundle() -> None:
    surface = build_validated_platform_boot_surface()
    report = validate_platform_boot_surface(surface)
    assert report.api_security_owner_bundle_shared is True
    assert report.is_valid is True
