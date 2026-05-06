from runtime.platform.business_memory.semantics import (
    counts_as_failure,
    counts_as_operator_handoff,
    counts_as_success,
    infer_memory_status,
)


def test_infer_memory_status_prefers_operator_required() -> None:
    assert infer_memory_status({'attempted': True, 'operator_required': True}) == 'operator_required'


def test_semantics_distinguish_success_failure_and_handoff() -> None:
    assert counts_as_success('verified') is True
    assert counts_as_failure('verification_failed') is True
    assert counts_as_operator_handoff('approval_required') is True
    assert counts_as_failure('attempted') is False
