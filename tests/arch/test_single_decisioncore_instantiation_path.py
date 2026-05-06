from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED = {
    'core/ai/decision_core.py',
    'runtime/boot/boot_core_assembly.py',
    'runtime/boot/boot_decision_core.py',
    'runtime/platform/support/optimization/self_optimization_loop.py',
}


def test_decisioncore_instantiation_is_kept_to_canonical_paths() -> None:
    offenders: list[str] = []
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith('tests/') or rel.startswith('runtime/platform/support/'):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == 'DecisionCore' and rel not in ALLOWED:
                    offenders.append(rel)
                    break

    assert offenders == [], offenders
