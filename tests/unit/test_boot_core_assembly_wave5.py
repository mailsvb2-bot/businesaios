from __future__ import annotations

from types import SimpleNamespace

from runtime.boot.boot_core_assembly import build_core_assembly


def test_build_core_assembly_uses_canonical_runtime_infra_builder(monkeypatch):
    seen = {}

    monkeypatch.setattr('runtime.boot.boot_core_assembly.build_survival_and_economics', lambda: (object(), object()))
    monkeypatch.setattr('runtime.boot.boot_core_assembly.build_decision_core', lambda **kwargs: (object(), object()))
    monkeypatch.setattr('runtime.boot.boot_core_assembly.build_guard', lambda **kwargs: object())
    monkeypatch.setattr('runtime.boot.boot_core_assembly.build_reward_and_learning_components', lambda **kwargs: (object(), object(), object()))

    def _fake_build_runtime_infra(**kwargs):
        seen['kwargs'] = kwargs
        return object()

    monkeypatch.setattr('runtime.boot.boot_core_assembly.build_runtime_infra', _fake_build_runtime_infra)
    monkeypatch.setattr('runtime.boot.boot_core_assembly.build_executor', lambda **kwargs: kwargs['runtime_infra'])

    runtime_infra = SimpleNamespace(
        ledger=object(),
        snapshot_store=object(),
        outbox=object(),
        payment_outbox=object(),
        settings_gateway=object(),
        messaging_policy_event_store=object(),
        messaging_policy_read_service=object(),
        telegram_outbound_queue=object(),
    )
    args = SimpleNamespace(
        policy_selector=object(),
        keyring=object(),
        schemas=object(),
        event_log=object(),
        decision_archive=object(),
        issuer_id='issuer',
        runtime_infra=runtime_infra,
        handlers=object(),
        policy_registry=object(),
        model_registry=object(),
        delivery_state=object(),
    )

    asm = build_core_assembly(args=args)
    assert asm.executor is not None
    assert seen['kwargs']['delivery_state'] is args.delivery_state
    assert seen['kwargs']['telegram_outbound_queue'] is runtime_infra.telegram_outbound_queue
