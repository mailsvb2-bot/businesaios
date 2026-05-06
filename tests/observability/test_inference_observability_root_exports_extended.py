from observability import (
    InferenceBudgetBurnEvent,
    InferenceBudgetBurnLog,
    InferenceCapacityTrace,
    InferenceCapacityTraceStore,
    InferenceEscalationAuditEvent,
    InferenceEscalationAuditLog,
    InferenceProviderHealthEvent,
    InferenceProviderHealthLog,
    InferenceRuntimeSummaryService,
    InferenceVerificationEvent,
    InferenceVerificationLog,
)


def test_inference_observability_root_exports_are_complete() -> None:
    assert InferenceBudgetBurnEvent is not None
    assert InferenceBudgetBurnLog is not None
    assert InferenceCapacityTrace is not None
    assert InferenceCapacityTraceStore is not None
    assert InferenceEscalationAuditEvent is not None
    assert InferenceEscalationAuditLog is not None
    assert InferenceProviderHealthEvent is not None
    assert InferenceProviderHealthLog is not None
    assert InferenceRuntimeSummaryService is not None
    assert InferenceVerificationEvent is not None
    assert InferenceVerificationLog is not None
