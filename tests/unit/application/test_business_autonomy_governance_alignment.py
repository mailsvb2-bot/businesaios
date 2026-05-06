from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers


def test_business_autonomy_governance_alignment_preview() -> None:
    handlers = build_business_autonomy_route_handlers()
    alignment = handlers.get_governance_alignment("metrotherapy")
    assert alignment["business_id"] == "metrotherapy"
    assert "execution_verdict" in alignment
    assert "normalized_request" in alignment
    assert "approval" in alignment["execution_verdict"]
