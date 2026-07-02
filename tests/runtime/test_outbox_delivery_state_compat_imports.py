from __future__ import annotations


def test_outbox_delivery_state_compat_imports_policy_from_canonical_owner() -> None:
    from runtime.platform.delivery_state_policy import DeliveryStatePolicy as CanonicalPolicy
    from runtime.platform.outbox import delivery_state as compat

    assert compat.DeliveryStatePolicy is CanonicalPolicy
    assert compat.DEFAULT_DELIVERY_STATE_POLICY.finalized_phase == compat.FINALIZED_PHASE
    assert callable(compat.open_delivery_state)
