from pathlib import Path


def test_boot_public_api_is_now_installed_from_package_root() -> None:
    text = Path("boot/__init__.py").read_text(encoding="utf-8")
    assert 'CANON_BOOT_PUBLIC_API_DIRECT_OWNER_DELEGATION = True' in text
    assert 'CANON_BOOT_PUBLIC_API_COMPAT_SHELL = True' in text
    assert 'install_public_api_alias(__name__)' in text
    assert 'runtime.bootstrap.sovereign_bootstrap' not in text
    assert 'boot.app_public_api' not in text
    assert 'boot.http_public_api' not in text
    assert 'boot.runtime_public_api' not in text
    assert not Path('boot/public_api.py').exists()
