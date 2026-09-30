from __future__ import annotations

from scripts.ci.targeted_domain_ci import touched_domains


def test_core_payment_roots_are_billing_domain() -> None:
    changed = [
        "core/payments/yookassa_webhook.py",
        "core/economics/brain.py",
        "core/billing/invoice_projection.py",
    ]

    assert touched_domains(changed) == ["billing"]


def test_unknown_core_paths_do_not_trigger_billing_domain() -> None:
    assert touched_domains(["core/unrelated/module.py"]) == []



def test_capability_and_autonomy_roots_trigger_targeted_domain() -> None:
    changed = [
        "application/business_autonomy/integration_capability_catalog.py",
        "application/autonomy/autonomy_state_assembly.py",
        "runtime/business_autonomy/provider_live_probe_runtime.py",
    ]

    assert touched_domains(changed) == ["capability_autonomy"]
