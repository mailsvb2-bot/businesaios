from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_executor_records_inference_audit_without_owning_routing() -> None:
    path = PROJECT_ROOT / 'runtime' / 'executor.py'
    text = path.read_text(encoding='utf-8')
    assert '_record_inference_selection_audit' in text
    assert '_record_inference_verification_audit' in text
    assert 'InferenceCapacityRouter(' not in text
    assert 'InferenceDispatchOrchestrator(' not in text
