from __future__ import annotations


class InstantMatchFlow:
    def start(self, request_text: str) -> dict[str, object]:
        return {
            'flow': 'instant_match',
            'text': str(request_text),
            'mode': 'preview_only',
            'decision_path': 'demand_decision_required',
        }
