from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


TARGETS = [
    "runtime/platform/config/settings_loader.py",
    "runtime/platform/config/env_tenant_config.py",
    "connectors/platform/ads/vault_env.py",
    "core/autopilot/loader.py",
    "core/read_model/cache.py",
    "core/tenancy/scope.py",
    "runtime/enforcement/world_model_pin_guard.py",
    "runtime/read_models/cache_window.py",
    "runtime/boot/_boot_utils.py",
]


def test_selected_files_no_raw_os_getenv_wave15() -> None:
    for rel in TARGETS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "os.getenv(" not in text, rel


def test_runtime_boot_env_is_canonical_wrapper_wave15() -> None:
    text = (ROOT / "runtime/boot/env.py").read_text(encoding="utf-8")
    assert "from runtime.platform.config.env_flags import env_bool as _env_bool" in text
    assert "from runtime.platform.config.env_flags import env_float as _env_float" in text
    assert "from runtime.platform.config.env_flags import env_int as _env_int" in text
    assert "os.getenv(" not in text
