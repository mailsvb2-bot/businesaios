from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def test_retry_learning_engine_does_not_import_decision_or_execution_owners() -> None:
    content = _read('application/learning/retry_learning_engine.py')
    forbidden = (
        'DecisionCore',
        'decision_core',
        'ClosedLoopOrchestrator',
        'AutonomyLoop',
        'runtime.executor',
        'ExecutionCapabilityRouter',
    )
    for token in forbidden:
        assert token not in content


def test_only_allowed_surfaces_import_retry_learning_engine() -> None:
    allowed = {
        'application/learning/retry_learning_engine.py',
        'execution/self_healing_retry.py',
        'execution/headless_boot.py',
    }
    offenders: list[str] = []
    for path in ROOT.rglob('*.py'):
        relative = str(path.relative_to(ROOT))
        if '/tests/' in f'/{relative}':
            continue
        if relative in allowed:
            continue
        content = path.read_text(encoding='utf-8')
        if 'from application.learning.retry_learning_engine import' in content or 'import application.learning.retry_learning_engine' in content:
            offenders.append(relative)
    assert offenders == []
