from __future__ import annotations

from canon.runtime_state_enrichment_rules import assert_runtime_enrichment_payload


def test_runtime_state_enrichment_payload_rejects_candidate_control() -> None:
    try:
        assert_runtime_enrichment_payload(
            {
                "external_world_state_features": {},
                "candidate_ids": ("a", "b"),
            }
        )
    except RuntimeError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
