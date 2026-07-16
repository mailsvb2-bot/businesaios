from __future__ import annotations

import sys

import scripts.ci.step_verify_release as verify_release_step


def test_canonical_python_env_uses_current_interpreter() -> None:
    assert verify_release_step._canonical_python_env() == {"PYTHON_BIN": sys.executable}
