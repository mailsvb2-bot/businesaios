from __future__ import annotations

from pathlib import Path

import core.ai as core_ai
import pytest

RESET_HOOK = "_reset_decision_core_singleton_for_tests"
ALLOWED_FORMAL_CALLER = "formal/regression_gate/project_snapshot_bundle.py"


@pytest.mark.lock
def test_decision_core_reset_is_not_a_public_api() -> None:
    assert RESET_HOOK not in core_ai.__all__
    assert "reset_decision_core_singleton" not in core_ai.__dict__


@pytest.mark.lock
def test_production_code_cannot_reference_the_test_reset_hook() -> None:
    offenders: list[str] = []
    for path in Path(".").rglob("*.py"):
        relative = path.as_posix().removeprefix("./")
        if relative == "core/ai/__init__.py":
            continue
        if relative.startswith("tests/"):
            continue
        if relative == ALLOWED_FORMAL_CALLER:
            continue
        text = path.read_text(encoding="utf-8")
        if RESET_HOOK in text:
            offenders.append(relative)

    assert offenders == [], (
        "production DecisionCore reset references found: "
        + ", ".join(sorted(offenders))
    )
