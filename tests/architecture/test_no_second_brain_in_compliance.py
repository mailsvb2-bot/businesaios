from pathlib import Path


FORBIDDEN_TOKENS = (
    'DecisionCore(',
    'class DecisionCore',
    'plan_next_goal',
    'business_strategy',
    'goal_optimizer',
    'autonomous_planner',
)


def test_compliance_namespace_does_not_introduce_second_brain() -> None:
    root = Path(__file__).resolve().parents[2]
    compliance_dir = root / 'compliance'
    assert compliance_dir.exists(), 'compliance namespace must exist'

    offenders: list[str] = []
    for path in compliance_dir.rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        for token in FORBIDDEN_TOKENS:
            if token in text:
                offenders.append(f'{path}: {token}')

    assert not offenders, 'Compliance namespace must stay policy-only:\n' + '\n'.join(offenders)
