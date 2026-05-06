from __future__ import annotations

from execution.optimization.feedback_pipeline import FeedbackPipeline
from execution.optimization.noise_guard import FeedbackNoiseGuard, NoiseMemory


def test_noise_guard_rejects_duplicate_feedback() -> None:
    guard = FeedbackNoiseGuard()
    memory = NoiseMemory()
    observation = {
        'verification_confidence': 0.9,
        'latency_ms': 1200.0,
        'cost': 12.0,
        'fingerprint': 'fp-1',
        'identity_complete': True,
    }
    assert guard.evaluate(observation=observation, memory=memory).accepted is True
    guard.commit(observation=observation, memory=memory)
    verdict = guard.evaluate(observation=observation, memory=memory)
    assert verdict.accepted is False
    assert verdict.reason == 'duplicate_feedback'


def test_noise_guard_rejects_low_confidence_feedback() -> None:
    guard = FeedbackNoiseGuard()
    verdict = guard.evaluate(observation={'verification_confidence': 0.12, 'latency_ms': 900.0, 'cost': 8.0, 'fingerprint': 'fp-low-confidence', 'identity_complete': True}, memory=NoiseMemory())
    assert verdict.accepted is False
    assert verdict.reason == 'low_verification_confidence'


def test_feedback_pipeline_marks_incomplete_identity() -> None:
    pipeline = FeedbackPipeline()
    observation = pipeline.normalize(feedback={'tenant_id': '', 'business_id': 'business-1', 'capability_key': 'launch_campaign', 'route_key': 'ads/google', 'action_type': 'launch_campaign', 'executed': True, 'verified': True, 'verification_confidence': 0.9})
    assert observation.identity_complete is False
