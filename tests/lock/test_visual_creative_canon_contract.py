from __future__ import annotations

from pathlib import Path

from runtime.boot.actions_registry import get_spec

ROOT = Path(__file__).resolve().parents[2]


def test_visual_creative_keeps_single_decision_and_execution_authority() -> None:
    handler = (ROOT / "runtime/handlers/visual_creative_gateway.py").read_text(encoding="utf-8")
    client = (ROOT / "runtime/_internal/effects_clients/visual_gateway_client.py").read_text(encoding="utf-8")
    domain = (ROOT / "runtime/_internal/effects_domains/visual_creative_gateway.py").read_text(encoding="utf-8")
    combined = "\n".join((handler, client, domain))
    assert "DecisionCore(" not in combined
    assert "RuntimeExecutor(" not in combined
    assert "choose_provider" not in combined
    assert "select_provider" not in combined
    assert "provider_score" not in combined
    assert "source\": \"visual_creative_gateway" not in domain
    assert '"source": "connector"' in domain


def test_visual_creative_registry_contract_is_external_generate_and_advisory_poll() -> None:
    generate = get_spec("visual_creative_generate@v1")
    poll = get_spec("visual_creative_poll@v1")
    assert generate.execution_category == "external_effect"
    assert generate.external_confirmation_mode == "required"
    assert generate.requires_idempotency_key is True
    assert poll.execution_category == "advisory"
    assert poll.external_confirmation_mode == "not_required"
    assert poll.requires_idempotency_key is False
