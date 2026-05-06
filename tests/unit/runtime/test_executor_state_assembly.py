from __future__ import annotations

from runtime.execution.executor_state import RuntimeExecutorState
from runtime.executor_runtime_support import build_executor_state


class _Handlers:
    pass


class _EventLog:
    pass


class _PolicyRegistry:
    pass


class _Guard:
    pass


class _Bundle:
    def __init__(self) -> None:
        self.effects = object()
        self.cap_token = object()


class _Infra:
    def __init__(self) -> None:
        self.effect_outbox = object()
        self.snapshot_archive = object()
        self.delivery_state = object()
        self.decision_ledger = object()
        self.payments_outbox = object()
        self.telegram_outbound_queue = object()
        self.settings_store = object()
        self.messaging_policy_store = object()
        self.messaging_policy_reader = object()


def test_build_executor_state_reuses_prebuilt_runtime_infra(monkeypatch) -> None:
    runtime_infra = _Infra()
    bundle = _Bundle()

    monkeypatch.setattr(
        'runtime.executor_runtime_support.build_executor_effects_bundle',
        lambda *, event_log, policy_registry, infra: bundle,
    )

    state = build_executor_state(
        guard=_Guard(),
        handlers=_Handlers(),
        event_log=_EventLog(),
        policy_registry=_PolicyRegistry(),
        reward_engine=None,
        learning_system=None,
        decision_core=None,
        runtime_infra=runtime_infra,
        ledger=None,
        snapshot_store=None,
        outbox=None,
        payment_outbox=None,
        settings_gateway=None,
        messaging_policy_event_store=None,
        messaging_policy_read_service=None,
        delivery_state=None,
        telegram_outbound_queue=None,
        decision_archive=None,
        constitution=None,
        max_meta_depth=3,
        economic_layer=None,
    )

    assert isinstance(state, RuntimeExecutorState)
    assert state.infra is runtime_infra
    assert state.snapshot_store is runtime_infra.snapshot_archive
    assert state.effects is bundle.effects
    assert state.cap_token is bundle.cap_token
    assert state.max_meta_depth == 3
