from __future__ import annotations

from governance.time_scale import TimeScale, assert_action_allowed


def test_action_matrix_runtime_allows_known_actions():
    # Must not raise for allowed runtime actions
    for action in [
        "noop@v1",
        "send_message@v1",
        "capture_payment@v1",
        "grant_access@v1",
        "deploy_policy@v1",
        "rollback_policy@v1",
    ]:
        assert_action_allowed(action, TimeScale.RUNTIME)


def test_action_matrix_blocks_dangerous_on_fast_scales():
    # Fast loops must not be able to run side-effects by action even if code tries.
    for ts in [TimeScale.ONLINE_LEARNING, TimeScale.OFFLINE_TRAINING]:
        try:
            assert_action_allowed("capture_payment@v1", ts)
            assert False, "expected forbidden"
        except RuntimeError as e:
            assert "ACTION_FORBIDDEN_ON_TIMESCALE" in str(e)
