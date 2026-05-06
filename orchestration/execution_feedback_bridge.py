from __future__ import annotations

from typing import Protocol

from contracts.action_result import ActionResult


class FeedbackRunPort(Protocol):
    def run(self, execution_result: ActionResult) -> dict: ...


class ExecutionToFeedbackFlow:
    def run(self, execution_result: ActionResult, feedback_pipeline: FeedbackRunPort) -> dict:
        return feedback_pipeline.run(execution_result)
