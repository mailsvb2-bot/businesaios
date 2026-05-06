from __future__ import annotations

from execution.inference_execution_result_contract import InferenceExecutionRecord


CANON_STORAGE_INFERENCE_EXECUTION_RECORD_REPOSITORY = True


class InferenceExecutionRecordRepository:
    def __init__(self) -> None:
        self._records: list[InferenceExecutionRecord] = []

    def append(self, record: InferenceExecutionRecord) -> None:
        self._records.append(record)

    def list_records(self) -> tuple[InferenceExecutionRecord, ...]:
        return tuple(self._records)
