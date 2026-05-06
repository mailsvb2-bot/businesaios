from runtime.boot.web.observability_boot_plan import BootResultItem, MessagingPolicyObservabilityBootResult


def test_boot_result_collects_booted_keys():
    result = MessagingPolicyObservabilityBootResult(
        items=(
            BootResultItem(key='a', enabled=True, booted=True),
            BootResultItem(key='b', enabled=True, booted=False),
            BootResultItem(key='c', enabled=False, booted=False),
        )
    )
    assert result.booted_keys == ('a',)
