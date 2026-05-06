from pathlib import Path


def test_bootstrap_surfaces_thread_shared_security_owner_bundle() -> None:
    system_text = Path('bootstrap/system_boot_surface.py').read_text(encoding='utf-8')
    runtime_text = Path('bootstrap/runtime_boot.py').read_text(encoding='utf-8')
    services_text = Path('runtime/boot/system_builder_parts/runtime_services.py').read_text(encoding='utf-8')
    result_builder_text = Path('runtime/boot/system_builder_parts/runtime_services_result_builder.py').read_text(encoding='utf-8')

    assert 'shared_runtime_payload' in runtime_text
    assert 'runtime_surface.shared_runtime_payload()' in system_text
    assert "ctx.set_value('api_security_owner_bundle'" in services_text
    assert "security_services = {'api_security_owner_bundle': security_surface.api_security_owner_bundle}" in services_text
    assert 'api_security_owner_bundle=(dict(security_services or {})).get' in result_builder_text
