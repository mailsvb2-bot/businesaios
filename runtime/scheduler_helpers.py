from __future__ import annotations

import logging
from typing import Any

from ml.policy_promotion_guard import EvaluationSnapshot
from runtime.observability.error_handling import warning_throttled
from runtime.tenancy import current_tenant_id
from runtime.world_state import WorldStateV1

log = logging.getLogger(__name__)


def log_exception_throttled(logger: logging.Logger, event: str, exc: Exception) -> None:
    warning_throttled(logger, event, exc, throttle_ms=30_000)


def build_system_world_state(*, now_ms: int, safe_mode: bool, proposal: dict[str, Any]) -> WorldStateV1:
    return WorldStateV1(
        schema_version=1,
        user={"role": "system"},
        session={},
        product={"name": "BusinesAIOS Workspace"},
        economy={},
        timestamp_ms=now_ms,
        tenant_id=current_tenant_id(),
        user_id="system",
        safe_mode=bool(safe_mode),
        deployment_proposal=dict(proposal or {}),
    )


def build_baseline_evaluation(*, state: Any, metrics: dict[str, Any]) -> EvaluationSnapshot:
    return EvaluationSnapshot(
        policy_id=str(state.active_policy_id),
        mean_reward=float(metrics.get("offline_mean_reward", 0.0) or 0.0),
        reward_std=0.0,
        samples=max(1, int(metrics.get("online_n", 0.0) or 0.0)),
    )


def build_candidate_evaluation(*, policy_id: str, train_metrics: dict[str, Any]) -> EvaluationSnapshot:
    return EvaluationSnapshot(
        policy_id=str(policy_id),
        mean_reward=float(train_metrics.get("offline_mean_reward", 0.0) or 0.0),
        reward_std=0.0,
        samples=max(1, int(train_metrics.get("n", 0) or 0)),
    )


def cleanup_rollout(manager: Any, rollout_id: str | None) -> str | None:
    if not rollout_id:
        return None
    try:
        manager.delete_rollout(rollout_id)
    except AttributeError as exc:
        warning_throttled(log, 'runtime.scheduler.cleanup_rollout.missing_delete', exc, throttle_ms=30_000)
    except Exception as exc:
        warning_throttled(log, 'runtime.scheduler.cleanup_rollout.failed', exc, throttle_ms=30_000)
    return None
