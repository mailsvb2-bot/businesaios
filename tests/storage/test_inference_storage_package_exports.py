from storage import InferenceExecutionRecordRepository


def test_storage_package_exports_inference_execution_repository() -> None:
    assert InferenceExecutionRecordRepository is not None
