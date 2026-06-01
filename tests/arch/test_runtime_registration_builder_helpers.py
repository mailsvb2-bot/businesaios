from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRATIONS_DIR = ROOT / 'boot' / 'registrations'

ALLOWED_DIRECT_REGISTRY_GETS = {
    'register_decision_core.py',
    'register_governance.py',
    '_shared.py',
}

ALLOWED_DIRECT_REGISTER_RUNTIME_SERVICE = {
    'register_action_executor.py',
    'register_decision_core.py',
    'register_governance.py',
    '_shared.py',
}


def test_catalog_backed_registration_modules_use_builder_helper() -> None:
    offenders: list[str] = []
    for path in sorted(REGISTRATIONS_DIR.glob('register_*.py')):
        if path.name in ALLOWED_DIRECT_REGISTRY_GETS:
            continue
        text = path.read_text(encoding='utf-8')
        if 'registry.get(' in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, (
        'Registration wrappers should resolve dependencies through '
        'boot.registrations._shared.register_built_runtime_service: '
        + ', '.join(offenders)
    )


def test_simple_registration_modules_use_singleton_helper() -> None:
    target_files = {
        'register_action_budget.py',
        'register_kill_switch.py',
        'register_observability.py',
        'register_reward.py',
        'register_risk.py',
        'register_simulation.py',
    }
    offenders: list[str] = []
    for path in sorted(REGISTRATIONS_DIR.glob('register_*.py')):
        if path.name not in target_files:
            continue
        text = path.read_text(encoding='utf-8')
        if 'register_runtime_singleton(' not in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, (
        'Simple singleton registrations should use '
        'boot.registrations._shared.register_runtime_singleton: '
        + ', '.join(offenders)
    )
