from interfaces.api.execute_action_stack_bundle import build_execute_action_stack_bundle
from observability.action_audit_log import ActionAuditLog


class _App:
    def execute_action(self, **kwargs):
        return {'ok': True, 'action': kwargs['action']}


class _Store:
    def __init__(self):
        self.values = {}
    def get(self, key):
        return self.values.get(key)
    def set(self, key, value):
        self.values[key] = value
    def delete(self, key):
        self.values.pop(key, None)


class _RetrySpec:
    max_attempts = 1
    delay_seconds = 0.0


class _RetryPolicy:
    spec = _RetrySpec()
    def run(self, fn):
        return fn()


class _Idempotency:
    def __init__(self):
        self._values = {}
    def status(self, *, key):
        return 'completed' if key in self._values else 'missing'
    def run(self, *, key, fn):
        if key in self._values:
            return self._values[key]
        value = fn()
        self._values[key] = value
        return value


class _GuardrailDecision:
    allowed = True
    reasons = ()


class _Guardrails:
    def evaluate(self, **kwargs):
        return _GuardrailDecision()


def test_build_execute_action_stack_bundle_returns_linear_stack() -> None:
    bundle = build_execute_action_stack_bundle(
        application_service=_App(),
        retry_policy=_RetryPolicy(),
        idempotency=_Idempotency(),
        action_audit_log=ActionAuditLog(),
        guardrails=_Guardrails(),
        tenant_quota_guard=None,
        quota_dimension='actions_per_hour',
        quota_amount=1.0,
        consume_quota_after_success_only=True,
    )
    assert bundle.stack.control_plane is bundle.control_plane
    assert bundle.control_plane.handler is bundle.guarded_handler
    assert bundle.guarded_handler.handler is bundle.handler
    assert bundle.execution_path_lock is not None
