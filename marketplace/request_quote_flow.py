from __future__ import annotations

"""Canonical marketplace quote-request flow.

This module keeps a *single* user-facing surface while preserving two valid
states of the system:

1. When the DecisionCore singleton is wired and exposes canonical
   ``optimize()``, the flow delegates to the marketplace demand pipeline.
2. When the runtime has not been wired yet, the flow remains explicitly
   preview-only instead of inventing a second execution path.

That keeps one boundary and avoids hidden fallback business logic.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from marketplace.demand_pipeline import process_demand


@dataclass(frozen=True)
class QuoteRequestPreview:
    payload: Mapping[str, Any]
    mode: str = "preview_only"
    decision_path: str = "demand_decision_required"

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "decision_path": self.decision_path,
            **dict(self.payload),
        }


class RequestQuoteFlow:
    """Thin boundary over the canonical demand pipeline."""

    def start(self, request_text: str) -> dict[str, Any]:
        payload = {
            "flow": "quote_request",
            "text": str(request_text),
            "source_surface": "request_quote_flow",
        }
        try:
            result = process_demand(payload)
        except RuntimeError as exc:
            if str(exc) != "DECISIONCORE_NOT_INITIALIZED":
                raise
            return QuoteRequestPreview(payload=payload).as_dict()
        return result if isinstance(result, dict) else {"result": result}


def build_quote_request_preview(payload: Mapping[str, Any]) -> QuoteRequestPreview:
    return QuoteRequestPreview(payload=dict(payload))


def execute_request_quote_flow(*args: Any, **kwargs: Any) -> dict[str, Any]:
    payload = kwargs.get("payload") if "payload" in kwargs else (args[0] if args else {})
    if isinstance(payload, Mapping):
        text = payload.get("text") or payload.get("input") or payload.get("request_text") or ""
    else:
        text = payload
    return RequestQuoteFlow().start(str(text))


__all__ = [
    "QuoteRequestPreview",
    "RequestQuoteFlow",
    "build_quote_request_preview",
    "execute_request_quote_flow",
]
