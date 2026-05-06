from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_no_direct_capability_health_store_usage_outside_owner_surfaces() -> None:
    execution_dir = ROOT / 'execution'
    offenders: list[str] = []
    for path in execution_dir.glob('*.py'):
        text = path.read_text(encoding='utf-8')
        if 'FileCapabilityHealthStore' not in text:
            continue
        if path.name in {'capability_health_scoring.py', 'capability_health_registry.py'}:
            continue
        offenders.append(path.name)
    assert offenders == []
