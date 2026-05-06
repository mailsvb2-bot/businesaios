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


def test_register_decision_core_remains_only_boot_compat_owner() -> None:
    text = Path('boot/registrations/register_decision_core.py').read_text(encoding='utf-8')
    assert 'def decide_and_execute(self, action: object) -> dict:' in text
    assert 'self.governance_chain.evaluate(action)' in text
    assert 'self.action_executor.execute(action)' in text
