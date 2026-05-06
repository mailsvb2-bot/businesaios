from __future__ import annotations

from execution.runners._external_effector_runner import ExternalEffectorRunner


CANON_RUNNER_EXECUTION_SEMANTICS = True


class Runner(ExternalEffectorRunner):
    def __init__(self) -> None:
        super().__init__(action_type="update_audience")
