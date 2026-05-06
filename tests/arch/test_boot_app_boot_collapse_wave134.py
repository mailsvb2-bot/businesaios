from pathlib import Path


def test_internal_boot_shims_stop_reusing_boot_app_boot_surface_alias() -> None:
    http_text = Path("boot/http_boot.py").read_text(encoding="utf-8")
    telegram_text = Path("boot/telegram_boot.py").read_text(encoding="utf-8")

    assert 'boot.app_boot", "boot_application' not in http_text
    assert 'from boot.app_boot import boot_application' not in telegram_text
    assert 'from boot.app_boot_surface import build_app_boot_surface' in telegram_text
    assert 'build_http_boot_surface' in http_text
