from __future__ import annotations

"""Self-driving scheduler.

This module closes the canonical loop:

Policy -> Decision -> Action -> Reward -> Learning -> Deploy -> Next Decision

IMPORTANT:
- It does NOT bypass the Ring.
- It only turns LearningSystem proposals into a WorldState and calls DecisionCore.issue,
  then executes the resulting DecisionEnvelope via RuntimeExecutor.
- Feedback-loop guards are enforced before deploy proposals enter the DecisionCore.
"""

import logging
from dataclasses import dataclass

from runtime.autopilot_feedback_guard import AutopilotFeedbackGuard, AutopilotFeedbackGuardViolation
from runtime.canon import CANONICAL_DECISION_CORE_MODULE
from runtime.governance.auto_deploy_guard import build_auto_deploy_guard_from_env
from runtime.observability.error_handling import warning_throttled
from runtime.scheduler_parts.decision_request import request_scheduler_decision_execution

_AUTODEPLOY_GUARD = build_auto_deploy_guard_from_env()
_FEEDBACK_GUARD = AutopilotFeedbackGuard()
log = logging.getLogger(__name__)

CANON_RUNTIME_SELF_DRIVING_SCHEDULER_GATEWAY_ONLY = True
CANON_RUNTIME_SELF_DRIVING_SCHEDULER_NO_RAW_DECISION_ISSUE = True
CANON_RUNTIME_SELF_DRIVING_SCHEDULER_REQUEST_HELPER_ONLY = True


@dataclass
class SchedulerTickResult:
    ok: bool
    status: str
    decision_id: str | None = None


def tick_once(*, learning_system, decision_core, executor, decision_input_provider=None) -> SchedulerTickResult:
    proposal = learning_system.maybe_propose_deployment()
    if not proposal:
        return SchedulerTickResult(ok=True, status="no_proposal")

    try:
        _FEEDBACK_GUARD.validate_action_vs_evaluation(
            action_origin=CANONICAL_DECISION_CORE_MODULE,
            evaluation_origin="core.learning.learning_system",
        )
    except AutopilotFeedbackGuardViolation as exc:
        return SchedulerTickResult(ok=False, status=f"feedback_guard:{exc.__class__.__name__}")

    v = _AUTODEPLOY_GUARD.allow(proposal=proposal)
    if not v.ok:
        return SchedulerTickResult(ok=True, status=f"veto:{v.reason}")
    if proposal.get("kind") == "deploy" and v.rollout_pct is not None:
        proposal = {**proposal, "rollout_pct": int(v.rollout_pct)}

    ws = learning_system.build_deploy_world_state(proposal)
    res = request_scheduler_decision_execution(
        issuer=decision_core,
        executor=executor,
        world_state=ws,
        proposal=proposal,
        generated_at_ms=int(ws.timestamp_ms),
        safe_mode=bool(getattr(ws, "safe_mode", False)),
        decision_input_provider=decision_input_provider,
    )
    if res.ok and proposal.get("kind") == "deploy":
        try:
            _AUTODEPLOY_GUARD.note_deploy_executed()
        except Exception as exc:
            warning_throttled(log, 'runtime.self_driving_scheduler.note_deploy_executed', exc, throttle_ms=30_000)
    return SchedulerTickResult(ok=res.ok, status="executed", decision_id=res.decision_id)
