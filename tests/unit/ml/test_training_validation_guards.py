from __future__ import annotations

from ml.training.validation import TrainingValidation


def test_training_validation_handles_none_and_non_numeric_values() -> None:
    ok, issues = TrainingValidation().validate_metrics({'accuracy': None, 'coverage': 'bad', 'precision': object(), 'recall': float('inf')})
    assert ok is False
    assert 'missing_accuracy' in issues
    assert 'coverage_too_low' in issues
    assert 'precision_too_low' in issues
    assert 'recall_too_low' in issues


def test_training_validation_flags_out_of_range_values() -> None:
    ok, issues = TrainingValidation().validate_metrics({'accuracy': 1.5, 'coverage': 0.9, 'precision': 0.9, 'recall': 0.9})
    assert ok is False
    assert 'accuracy_out_of_range' in issues
