from __future__ import annotations

from application.learning.retry_taxonomy import RetryTaxonomy


def test_retry_taxonomy_marks_timeout_as_recoverable() -> None:
    taxonomy = RetryTaxonomy()
    result = taxonomy.classify(ok=False, error="timeout")
    assert result.kind == "recoverable"
    assert result.should_retry is True


def test_retry_taxonomy_marks_manual_review_as_operator_required() -> None:
    taxonomy = RetryTaxonomy()
    result = taxonomy.classify(ok=False, error="manual_review")
    assert result.kind == "operator_required"
    assert result.should_retry is False


def test_retry_taxonomy_marks_unknown_failure_as_non_recoverable() -> None:
    taxonomy = RetryTaxonomy()
    result = taxonomy.classify(ok=False, error="schema_mismatch")
    assert result.kind == "non_recoverable"
    assert result.should_retry is False
