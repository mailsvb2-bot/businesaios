from __future__ import annotations

from marketplace.instant_match_flow import InstantMatchFlow
from marketplace.request_quote_flow import RequestQuoteFlow


def test_marketplace_flows_do_not_emit_decisions() -> None:
    for flow in (InstantMatchFlow(), RequestQuoteFlow()):
        payload = flow.start('help me')
        assert payload['mode'] == 'preview_only'
        assert payload['decision_path'] == 'demand_decision_required'
        assert 'selected_business_id' not in payload
