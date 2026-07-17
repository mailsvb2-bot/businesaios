from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_SURFACES = (
    "core/ai/agi_decision_core.py",
    "core/decision/agi_decision_core.py",
    "execution/agi_executor.py",
    "execution/agi_action_selector.py",
    "execution/secondary_decision_loop.py",
    "learning/autonomous_brain.py",
    "bootstrap/secondary_decision_world_model.py",
    "bootstrap/agi_decision_core_adapter.py",
    "bootstrap/parallel_decision_adapter.py",
)


def test_no_second_brain_surfaces_are_added():
    for rel in FORBIDDEN_SURFACES:
        assert not Path(rel).exists(), (
            f"forbidden second-brain surface exists: {rel}"
        )


def _class_methods(path: str, class_name: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"), filename=path)
    classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    assert len(classes) == 1
    return {
        node.name
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def test_recommendation_service_cannot_restore_decision_authority() -> None:
    methods = _class_methods(
        "application/decision/decision_service.py",
        "DecisionService",
    )
    assert not ({"issue", "optimize", "decide"} & methods)

    contract = Path("application/decision/decision_contract.py").read_text(
        encoding="utf-8"
    )
    assert "build_executable_action" not in contract
    assert "ExecutableAction" not in contract


def test_application_dispatcher_cannot_decide_and_execute() -> None:
    dispatcher = Path(
        "application/decision/action_dispatcher.py"
    ).read_text(encoding="utf-8")
    ports = Path("application/decision/ports.py").read_text(
        encoding="utf-8"
    )

    assert "decide_and_execute" not in dispatcher
    assert "decide_and_execute" not in ports
    assert "execute(envelope)" in ports
