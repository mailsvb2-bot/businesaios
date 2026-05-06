from storage import CANON_STORAGE_NAMESPACE, CANON_STORAGE_PACKAGE_OWNER, InferenceExecutionRecordRepository


def test_inference_storage_root_owner_marker_present() -> None:
    assert CANON_STORAGE_NAMESPACE is True
    assert CANON_STORAGE_PACKAGE_OWNER is True
    assert InferenceExecutionRecordRepository is not None
