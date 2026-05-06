from pathlib import Path


def test_adaptive_optimization_never_imports_decisioncore() -> None:
    offenders = []
    for path in Path('execution/optimization').rglob('*.py'):
        text = path.read_text(encoding='utf-8')
        if 'DecisionCore' in text or 'decision_core' in text:
            offenders.append(str(path))
    assert offenders == []
