from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_boot_package_root_installs_alias_modules_for_internal_support_surfaces() -> None:
    text = _read("boot/__init__.py")
    for alias_name, owner in {
        "app_boot_guard": "bootstrap.app_boot_guard",
        "app_boot_observability": "bootstrap.app_boot_observability",
        "app_boot_result": "bootstrap.app_boot_result",
        "bootstrap_config_surface": "bootstrap.bootstrap_config_surface",
        "platform_boot_contract": "bootstrap.platform_boot_contract",
        "platform_boot_surface": "bootstrap.platform_boot_surface",
        "runtime_boot": "bootstrap.runtime_boot",
        "runtime_boot_guard": "bootstrap.runtime_boot_guard",
        "runtime_boot_manifest": "bootstrap.runtime_boot_manifest",
        "runtime_boot_report": "bootstrap.runtime_boot_report",
        "runtime_dependency_sets": "bootstrap.runtime_dependency_sets",
        "runtime_manifest_support": "bootstrap.runtime_manifest_support",
        "runtime_service_specs": "bootstrap.runtime_service_specs",
        "startup_pipeline": "bootstrap.startup_pipeline",
        "system_boot_surface": "bootstrap.system_boot_surface",
        "system_registry_boot": "bootstrap.system_registry_boot",
    }.items():
        assert f'"{alias_name}": "{owner}"' in text
    assert '_install_compat_aliases()' in text


def test_bootstrap_owner_surfaces_keep_internal_support_markers() -> None:
    manifest = _read("bootstrap/runtime_boot_manifest.py")
    report = _read("bootstrap/runtime_boot_report.py")
    app_guard = _read("bootstrap/app_boot_guard.py")
    app_observability = _read("bootstrap/app_boot_observability.py")
    http_surface = _read("bootstrap/http_boot_surface.py")
    platform_surface = _read("bootstrap/platform_boot_surface.py")
    platform_contract = _read("bootstrap/platform_boot_contract.py")
    system_surface = _read("bootstrap/system_boot_surface.py")
    system_registry = _read("bootstrap/system_registry_boot.py")
    assert "CANON_RUNTIME_BOOT_MANIFEST_INTERNAL_SUPPORT = True" in manifest
    assert "CANON_RUNTIME_BOOT_REPORT_INTERNAL_SUPPORT = True" in report
    assert "CANON_APP_BOOT_GUARD_FINAL_OWNER = True" in app_guard
    assert "CANON_APP_BOOT_OBSERVABILITY_FINAL_OWNER = True" in app_observability
    assert "CANON_HTTP_BOOT_SURFACE_INTERNAL_SUPPORT = True" in http_surface
    assert "CANON_PLATFORM_BOOT_SURFACE_INTERNAL_SUPPORT = True" in platform_surface
    assert "CANON_PLATFORM_BOOT_CONTRACT_INTERNAL_SUPPORT = True" in platform_contract
    assert "CANON_SYSTEM_BOOT_SURFACE_INTERNAL_SUPPORT = True" in system_surface
    assert "CANON_BOOT_SYSTEM_REGISTRY_INTERNAL_SUPPORT = True" in system_registry


def test_telegram_boot_stays_thin_legacy_shim() -> None:
    text = _read("boot/telegram_boot.py")
    assert "CANON_TELEGRAM_BOOT_THIN_SHIM = True" in text
    assert "CANON_TELEGRAM_BOOT_NO_RUNTIME_ASSEMBLY = True" in text
    assert "from boot.app_boot import boot_application" not in text
    assert "from boot.app_boot_surface import build_app_boot_surface" in text
