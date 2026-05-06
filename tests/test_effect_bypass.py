import pytest

from runtime.security.capability_gate import GuardedEffectsPort


class FakeEffects:
    def send_message(self, **kwargs):
        return True

    def capture_payment(self, **kwargs):
        return True

    def deploy_policy(self, **kwargs):
        return True

    def rollback_policy(self, **kwargs):
        return True


def test_real_effect_without_capability_fails():
    effects = GuardedEffectsPort("token", FakeEffects())

    with pytest.raises(RuntimeError):
        effects.send_message(decision_id="d", correlation_id="c", user_id="u1", text="hack")
