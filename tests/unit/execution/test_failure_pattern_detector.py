from __future__ import annotations

from application.learning.failure_pattern_detector import FailurePatternDetector


def test_failure_pattern_detector_detects_recurring_rate_limit_pattern() -> None:
    detector = FailurePatternDetector()
    report = detector.detect(
        tenant_id="tenant-1",
        business_id="biz-1",
        events=[
            {
                "tenant_id": "tenant-1",
                "business_id": "biz-1",
                "action_type": "launch_campaign",
                "retry_kind": "recoverable",
                "result_error": "rate_limit exceeded",
                "attempt_index": 1,
                "failed": True,
                "timestamp": "2026-04-01T10:00:00Z",
                "capability": "ads.launch",
            },
            {
                "tenant_id": "tenant-1",
                "business_id": "biz-1",
                "action_type": "launch_campaign",
                "retry_kind": "recoverable",
                "result_error": "rate_limit exceeded again",
                "attempt_index": 2,
                "failed": True,
                "timestamp": "2026-04-01T10:01:00Z",
                "capability": "ads.launch",
            },
        ],
    )
    assert report.recurring_pattern_count == 1
    assert report.patterns[0].error_family == "rate_limit"
    assert report.patterns[0].recurring is True
    assert report.patterns[0].recommended_backoff_floor_seconds >= 30
    assert report.patterns[0].must_not_issue_decision is True


def test_failure_pattern_detector_marks_policy_and_operator_pressure() -> None:
    detector = FailurePatternDetector()
    report = detector.detect(
        events=[
            {
                "action_type": "publish_offer",
                "retry_kind": "operator_required",
                "result_error": "permission denied",
                "attempt_index": 1,
                "failed": True,
                "blocked_by_policy": True,
                "approval_required": True,
                "capability": "publishing",
            }
        ]
    )
    pattern = report.patterns[0]
    assert pattern.should_open_operator_handoff is True
    assert pattern.policy_block_count == 1
    assert pattern.operator_required_count == 1


def test_failure_pattern_detector_bounds_timestamp_samples_and_error_length() -> None:
    detector = FailurePatternDetector()
    long_error = "transport failed " + ("x" * 500)
    events = []
    for index in range(20):
        events.append(
            {
                "action_type": "sync_crm",
                "retry_kind": "recoverable",
                "result_error": long_error,
                "attempt_index": index + 1,
                "failed": True,
                "timestamp": f"2026-04-01T10:{index:02d}:00Z",
                "capability": "crm.sync",
            }
        )

    report = detector.detect(events=events)

    assert len(report.patterns) == 1
    pattern = report.patterns[0]
    assert len(pattern.timestamps) <= 12
    assert len(pattern.sample_error) <= 280
    assert pattern.should_cooldown is True
