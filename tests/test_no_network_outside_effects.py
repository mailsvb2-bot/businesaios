from __future__ import annotations

from tests.business_autonomy.test_no_direct_network_outside_effects import (
    test_external_api_literals_are_only_in_sealed_effects_or_provider_transport as _assert_external_literals_sealed,
)
from tests.business_autonomy.test_no_direct_network_outside_effects import (
    test_no_direct_network_primitives_outside_sealed_effects_or_provider_transport as _assert_network_primitives_sealed,
)
from tests.business_autonomy.test_no_direct_network_outside_effects import (
    test_no_subprocess_curl_or_wget_outside_tests as _assert_no_network_subprocesses,
)


def test_no_network_outside_canonical_effect_and_provider_boundaries() -> None:
    """Keep one network policy and one scanner implementation repository-wide."""

    _assert_network_primitives_sealed()
    _assert_no_network_subprocesses()
    _assert_external_literals_sealed()
