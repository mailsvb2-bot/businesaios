from __future__ import annotations

from canon.runtime_packet_provider_rules import assert_runtime_packet_provider_api


def test_runtime_packet_provider_api_rejects_decision_methods() -> None:
    try:
        assert_runtime_packet_provider_api(("build", "decide"))
    except RuntimeError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
