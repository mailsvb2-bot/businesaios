from __future__ import annotations

from execution.runners._external_effector_runner import ExternalEffectorRunner


class Runner(ExternalEffectorRunner):
    def __init__(self) -> None:
        super().__init__(action_type="create_landing_page")
