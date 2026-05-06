def test_boot_module_exports():
    from runtime.boot.web.boot_observability import (
        MessagingPolicyObservabilityBootFlags,
        MessagingPolicyObservabilityBootResult,
        boot_messaging_policy_observability_fastapi,
        boot_messaging_policy_observability_flask,
    )

    assert MessagingPolicyObservabilityBootFlags is not None
    assert MessagingPolicyObservabilityBootResult is not None
    assert callable(boot_messaging_policy_observability_fastapi)
    assert callable(boot_messaging_policy_observability_flask)
