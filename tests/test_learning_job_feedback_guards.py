from __future__ import annotations

from dataclasses import dataclass

from runtime.scheduler import LearningJob


@dataclass
class _Model:
    model_id: str
    payload: dict
    metrics: dict


@dataclass
class _TrainResult:
    model: _Model


@dataclass
class _Verdict:
    ok: bool
    reason: str | None
    safe_rollout_pct: int


class _Builder:
    def build(self, start_ms: int, end_ms: int):
        return type("Snapshot", (), {"snapshot_id": "snap-1"})()


class _Trainer:
    def train(self, snapshot):
        return _TrainResult(_Model("m1", {"best_policy_id": "candidate@v1"}, {"offline_mean_reward": 1.2, "n": 50}))


class _Validator:
    def validate(self, model, baseline_metrics):
        return _Verdict(True, None, 10)


class _RolloutState:
    active_policy_id = "baseline@v1"
    candidate_policy_id = None
    status = "stable"


class _Rollout:
    def __init__(self):
        self._state = _RolloutState()
        self._metrics = {"offline_mean_reward": 1.0, "online_n": 100}

    def state(self):
        return self._state

    def baseline_metrics(self):
        return dict(self._metrics)

    def set_baseline_metrics(self, metrics):
        self._metrics = dict(metrics)

    def begin_rollout(self, candidate_policy_id, pct):
        self._state = type("State", (), {"active_policy_id": "baseline@v1", "candidate_policy_id": candidate_policy_id, "status": "rolling"})()


class _DecisionCore:
    def issue(self, ws):
        return type("Env", (), {"decision": type("Decision", (), {"decision_id": "d1"})()})()


class _Executor:
    def execute(self, env):
        return type("Result", (), {"ok": True, "decision_id": "d1"})()


class _EventStore:
    def load(self, start_ms, end_ms):
        return []


def test_learning_job_uses_feedback_guards():
    job = LearningJob(
        builder=_Builder(),
        trainer=_Trainer(),
        validator=_Validator(),
        rollout=_Rollout(),
        decision_core=_DecisionCore(),
        executor=_Executor(),
        event_store=_EventStore(),
    )
    res = job.run_once()
    assert res.status == "deploy_requested"
    assert job._active_rollout_id == "m1:candidate@v1"
