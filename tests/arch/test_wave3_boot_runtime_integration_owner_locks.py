from pathlib import Path


def test_boot_runtime_integration_surfaces_do_not_issue_raw_decisions() -> None:
    targets = (
        'runtime/boot/boot_executor.py',
        'runtime/boot/boot_decision_core.py',
        'runtime/boot/system_builder_parts/runtime_services.py',
        'runtime/boot/system_builder_finalize.py',
        'runtime/boot/assembly_runtime.py',
    )
    for rel in targets:
        text = Path(rel).read_text(encoding='utf-8')
        assert '.issue(' not in text, rel
        assert '.decide(' not in text, rel
        assert '.optimize(' not in text, rel


def test_register_decision_core_remains_only_boot_compat_registration() -> None:
    text = Path('boot/registrations/register_decision_core.py').read_text(encoding='utf-8')
    factory = Path('boot/factories/decision_core_factory.py').read_text(encoding='utf-8')
    assert 'return register_runtime_decision_execution_service(registry)' in text
    assert 'RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE' in text
    assert 'build_runtime_decision_execution_service(' in factory
    assert '.issue(' not in text
    assert '.decide(' not in text
