from __future__ import annotations
from dataclasses import asdict, is_dataclass


class FeedbackPipeline:
    def run(self, execution_result: object) -> dict:
        payload = asdict(execution_result) if is_dataclass(execution_result) else dict(execution_result)
        return {'feedback_kind': 'execution_feedback', 'execution_result': payload}
