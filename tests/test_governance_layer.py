from governance.constitution import Constitution, ConstitutionViolation
from governance.evolution_gate import EvolutionGate, EvolutionRejected, PolicyMetrics
from governance.self_driving_loop import PolicyMetrics as LoopMetrics
from governance.self_driving_loop import RollbackController, SelfDrivingLoop
from governance.survival_controller import GovernanceHealthState, SurvivalController
from governance.time_scale import TIME_SCALE_RULES, TimeScale


def test_constitution_requires_envelope():
    c = Constitution()
    try:
        c.assert_decision_envelope(None)
        assert False, "Expected ConstitutionViolation"
    except ConstitutionViolation:
        pass


def test_time_scale_rules_sane():
    assert TIME_SCALE_RULES[TimeScale.RUNTIME].allow_side_effects is True
    assert TIME_SCALE_RULES[TimeScale.EVOLUTION].require_human_review is True
    assert TIME_SCALE_RULES[TimeScale.OFFLINE_TRAINING].allow_side_effects is False


def test_evolution_gate_rejects_bad_metrics():
    gate = EvolutionGate()
    old = PolicyMetrics(reward=1.0, risk=0.01, stability=0.99)
    bad = PolicyMetrics(reward=1.001, risk=0.01, stability=0.99)  # gain too small
    try:
        gate.approve(old, bad)
        assert False, "Expected EvolutionRejected"
    except EvolutionRejected:
        pass


def test_survival_controller_assess():
    s = SurvivalController()
    assert s.assess(reward_drop=0.0, error_rate=0.0) == GovernanceHealthState.HEALTHY
    assert s.assess(reward_drop=0.2, error_rate=0.0) == GovernanceHealthState.DEGRADED
    assert s.assess(reward_drop=0.0, error_rate=0.5) == GovernanceHealthState.CRITICAL
    assert s.should_rollback() is True


def test_self_driving_loop_smoke():
    class _Store:
        def all(self):
            return [1.0, 2.0, 3.0]

    class _Trainer:
        def train(self, rewards):
            return {"policy": "new"}

    class _Eval:
        def evaluate(self, policy, rewards):
            # simple metric: mean reward
            r = sum(rewards) / len(rewards)
            return LoopMetrics(reward=float(r), risk=0.0, stability=1.0)

    class _Registry:
        def __init__(self):
            self._active = {"policy": "old"}

        @property
        def active(self):
            return self._active

        def swap(self, policy):
            self._active = policy

    class _Rollout:
        def approve(self, old, new):
            return True

    reg = _Registry()
    rb = RollbackController(reg)
    loop = SelfDrivingLoop(_Store(), _Trainer(), _Eval(), reg, _Rollout(), rb)
    assert loop.evolve() is True
    assert reg.active["policy"] == "new"
