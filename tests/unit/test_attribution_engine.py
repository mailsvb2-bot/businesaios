from attribution.attribution_engine import AttributionEngine


def _canonical_payload() -> dict:
    return {
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "goal_id": "goal-1",
        "decision_id": "decision-1",
        "action_id": "action-1",
        "interaction_id": "interaction-1",
        "customer_id": "customer-1",
        "conversion_id": "conversion-1",
        "payment_id": "payment-1",
        "outcome_id": "outcome:action-1",
        "verified": True,
        "evidence_refs": ("evidence-1",),
    }


def test_attribution_engine_returns_result():
    result = AttributionEngine().attribute({"channel": "ads"})
    assert result["kind"] == "attribution_result"


def test_canonical_attribution_requires_complete_verified_lineage_for_causal_upgrade():
    result = AttributionEngine().attribute_canonical(_canonical_payload())
    payload = result["payload"]
    assert payload["model"] == "canonical_lineage_v1"
    assert payload["complete_chain"] is True
    assert payload["missing_chain"] == []
    assert payload["causality_level"] == "likely_contributed"
    assert payload["chain"]["payment"] == "payment-1"


def test_canonical_attribution_does_not_overclaim_when_chain_is_incomplete():
    payload = _canonical_payload()
    payload.pop("conversion_id")
    payload["attribution_verified"] = True
    result = AttributionEngine().attribute_canonical(payload)["payload"]
    assert result["complete_chain"] is False
    assert result["missing_chain"] == ["conversion"]
    assert result["causality_level"] == "correlated"


def test_canonical_attribution_requires_explicit_proof_for_strong_and_experimental_levels():
    strong = _canonical_payload()
    strong["attribution_verified"] = True
    assert AttributionEngine().attribute_canonical(strong)["payload"]["causality_level"] == "likely_contributed"
    strong["attribution_proof_refs"] = ("evidence-1",)
    strong_result = AttributionEngine().attribute_canonical(strong)["payload"]
    assert strong_result["causality_level"] == "strongly_attributed"

    experiment = dict(strong)
    experiment["experiment_id"] = "experiment-1"
    experiment["experiment_validated"] = True
    assert AttributionEngine().attribute_canonical(experiment)["payload"]["causality_level"] == "strongly_attributed"
    experiment["experiment_evidence_refs"] = ("evidence-1",)
    experiment_result = AttributionEngine().attribute_canonical(experiment)["payload"]
    assert experiment_result["causality_level"] == "experimentally_validated"
