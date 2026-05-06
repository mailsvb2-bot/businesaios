from pathlib import Path


def test_runtime_services_builds_shared_security_boot_surface_once() -> None:
    text = Path('runtime/boot/system_builder_parts/runtime_services.py').read_text(encoding='utf-8')
    assert 'build_security_boot_surface' in text
