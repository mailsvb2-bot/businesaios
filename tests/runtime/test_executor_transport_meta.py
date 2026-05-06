from __future__ import annotations

from dataclasses import dataclass

from runtime.executor import RuntimeExecutor


@dataclass
class _Decision:
    decision_id: str = 'dec-1'
    correlation_id: str = 'corr-1'
    payload: dict | None = None


@dataclass
class _Env:
    decision: _Decision


class _Outbox:
    def get(self, *, tenant_id: str, message_id: str):
        class _Row:
            state = 'delivered'
            delivery_attempts = 1
            backend_name = 'runtime_executor'
            external_id = 'ext-1'
            effect_key = 'fx-1'
            effect_kind = 'runtime_effect'
            payload_digest = 'digest-1'
            delivered_at = None
            delivery_metadata = {'owner_id': 'runtime-executor'}
        return _Row()


def test_attach_effect_delivery_metadata_includes_handler_transport_meta() -> None:
    executor = object.__new__(RuntimeExecutor)
    executor._outbox = _Outbox()
    executor._reliability = None
    env = _Env(decision=_Decision(payload={'tenant_id': 'tenant-a'}))

    out = RuntimeExecutor._attach_effect_delivery_metadata(executor, env=env, output={'meta': {'mode': 'queued', 'delivery_key': 'k1'}})
    assert out['effect_delivery']['transport_meta']['mode'] == 'queued'
    assert out['effect_delivery']['transport_meta']['delivery_key'] == 'k1'
