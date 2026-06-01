from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_CALLS = {'DecisionCore', 'RuntimeDecisionCore', 'AutonomyAdvisorService'}
TARGETS = (
    PROJECT_ROOT / 'execution' / 'inference_dispatch_orchestrator.py',
    PROJECT_ROOT / 'execution' / 'inference_capacity_router.py',
    PROJECT_ROOT / 'runtime' / 'inference' / 'provisioning' / 'capacity_manager.py',
)


def test_inference_capacity_modules_do_not_instantiate_decision_owners() -> None:
    violations: list[str] = []
    for path in TARGETS:
        if not path.exists():
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                    violations.append(f'{path.as_posix()}:{node.lineno} forbidden call {func.id}')
        text = path.read_text(encoding='utf-8')
        assert 'second_brain' not in text
        assert 'strategy_memory' not in text
    assert not violations, '\n'.join(violations)
