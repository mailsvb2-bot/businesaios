from pathlib import Path


def _read(rel: str) -> str:
    return Path(rel).read_text(encoding="utf-8")


def test_boot_package_stays_lazy_compat_surface() -> None:
    text = _read("boot/__init__.py")
    assert 'CANON_BOOT_PACKAGE_LAZY_EXPORTS = True' in text
    assert 'CANON_BOOT_PACKAGE_DIRECT_OWNER_EXPORTS = True' in text
    assert 'CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.compose"' in text
    assert '"BuiltRuntime": ("runtime.bootstrap", "BuiltRuntime")' in text
    assert '"build_runtime": ("bootstrap.compose", "build_runtime")' in text
    assert 'import_module("boot.public_api")' not in text
    assert 'boot.runtime_orchestrator' not in text


def test_main_keeps_single_runtime_bootstrap_helper_and_no_boot_imports() -> None:
    text = _read("main.py")
    assert 'CANON_MAIN_RUNTIME_ENTRYPOINT = True' in text
    assert 'def _bootstrap_runtime_process() -> None:' in text
    assert '_telegram_ep().runtime_bootstrap()' in text
    assert 'from boot.' not in text


def test_runtime_entrypoint_shim_delegates_to_runtime_bootstrap() -> None:
    text = _read("runtime/entrypoints/telegram_longpoll.py")
    assert 'CANON_RUNTIME_ENTRYPOINT_THIN_SHIM = True' in text
    assert 'CANON_RUNTIME_ENTRYPOINT_BOOTSTRAP_DELEGATES_TO_SOVEREIGN_BOOTSTRAP = True' in text
    assert 'from runtime.bootstrap import bootstrap as _bootstrap' in text


def test_boot_self_check_is_internal_protocol_surface() -> None:
    text = _read("boot/self_check.py")
    assert "CANON_BOOT_SELF_CHECK_INTERNAL_SUPPORT = True" in text
    assert "CANON_BOOT_SELF_CHECK_NO_PUBLIC_ENTRYPOINT = True" in text
    assert "CANON_BOOT_SELF_CHECK_NO_RUNTIME_ASSEMBLY = True" in text
    assert "from runtime.runtime_orchestrator import RuntimeOrchestrator" not in text
    assert "class SupportsBootSelfCheck(Protocol)" in text


def test_runtime_integration_avoids_runtime_orchestrator_type_coupling() -> None:
    text = _read("boot/runtime_integration.py")
    assert "from boot.runtime_orchestrator import BuiltRuntime" not in text
    assert "CANON_RUNTIME_INTEGRATION_PROTOCOL_TYPED = True" in text
    assert "class SupportsBuiltRuntime(Protocol)" in text
