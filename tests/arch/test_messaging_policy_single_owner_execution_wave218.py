from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY_EXECUTION_OWNER = ROOT / 'runtime/_internal/effects_actions/telegram/messaging_parts/policy.py'
NON_OWNER_FILES = [
    ROOT / 'runtime/messaging_policy/resolver.py',
    ROOT / 'runtime/messaging/router.py',
    ROOT / 'runtime/messaging/dispatcher.py',
    ROOT / 'runtime/messaging_policy/discipline.py',
    ROOT / 'runtime/messaging_policy_events/execute_with_events.py',
]

def test_policy_execution_owner_file_exists_and_is_canonical() -> None:
    assert POLICY_EXECUTION_OWNER.exists()
    text = POLICY_EXECUTION_OWNER.read_text(encoding='utf-8')
    assert 'execute_with_policy' in text
    assert 'execute_delivery_path' in text
    assert 'MessagingPolicyResolver' in text
    assert 'load_channel_preference' in text
    assert 'execute_policy_plan_with_events' in text

def test_non_owner_files_do_not_become_delivery_path_orchestrators() -> None:
    offenders=[]
    forbidden_patterns=('execute_delivery_path(', 'load_channel_preference(', 'build_policy_event_recorder_from_runtime(')
    for path in NON_OWNER_FILES:
        if not path.exists():
            continue
        text=path.read_text(encoding='utf-8')
        for pattern in forbidden_patterns:
            if pattern in text:
                offenders.append(f'{path.as_posix()}: {pattern}')
    assert not offenders, offenders
