from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_second_capability_planner_owner_path() -> None:
    execution_dir = ROOT / 'execution'
    offenders: list[str] = []
    for path in execution_dir.glob('*.py'):
        if path.name in {'capability_aware_planning.py', 'capability_router.py'}:
            continue
        text = path.read_text(encoding='utf-8')
        if 'class CapabilityAwarePlanner' in text:
            offenders.append(path.name)
    assert offenders == []


def test_runtime_capability_snapshot_access_is_constrained() -> None:
    execution_dir = ROOT / 'execution'
    allowed = {'capability_router.py', 'autonomy_state_assembly.py'}
    offenders: list[str] = []
    for path in execution_dir.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        if 'runtime_capabilities' not in text:
            continue
        if path.name in allowed or path.name == 'capability_matrix.py' or path.name == 'capability_health_registry.py':
            continue
        if 'runtime_capabilities' in text:
            offenders.append(path.name)
    assert offenders == []
