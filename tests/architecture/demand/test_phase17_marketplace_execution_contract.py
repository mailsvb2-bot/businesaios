from __future__ import annotations

from pathlib import Path

import core.ai as ai
from marketplace.demand_pipeline import process_demand
from marketplace.request_quote_flow import RequestQuoteFlow


class _OptimizeOnlyCore:
    def __init__(self) -> None:
        self.calls = []

    def optimize(self, payload):
        self.calls.append(payload)
        return {"decision": "ok", "payload": payload}


class _DecideOnlyCore:
    def route(self, payload):
        return payload


def test_process_demand_requires_optimize_only() -> None:
    ai.reset_decision_core_singleton()
    ai.set_decision_core_singleton(_DecideOnlyCore())
    try:
        process_demand({"goal": "match"})
    except TypeError as exc:
        assert str(exc) == "canonical_decision_core_optimize_required"
    else:
        raise AssertionError("process_demand must reject non-optimize entrypoints")
    finally:
        ai.reset_decision_core_singleton()


def test_request_quote_flow_uses_canonical_demand_pipeline() -> None:
    core = _OptimizeOnlyCore()
    ai.reset_decision_core_singleton()
    ai.set_decision_core_singleton(core)
    result = RequestQuoteFlow().start("Need a local specialist")
    assert result["decision"] == "ok"
    assert core.calls == [
        {
            "flow": "quote_request",
            "text": "Need a local specialist",
            "source_surface": "request_quote_flow",
        }
    ]
    ai.reset_decision_core_singleton()


def test_catalog_uses_canonical_request_quote_flow_module() -> None:
    text = (Path(__file__).resolve().parents[3] / "marketplace" / "catalog.py").read_text(encoding="utf-8")
    assert "from marketplace.request_quote_flow import RequestQuoteFlow" in text
    assert 'preview_only' not in text
    assert 'demand_decision_required' not in text
