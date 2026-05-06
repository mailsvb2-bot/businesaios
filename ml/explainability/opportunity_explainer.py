from __future__ import annotations

from kernel.decision_candidate import DecisionCandidate

_REDACTED_EXACT_KEYS = {'phone', 'email', 'contact', 'customer_id', 'session_id'}
_REDACTED_SUBSTRINGS = ('phone', 'email', 'contact', 'customer', 'session')


class OpportunityExplainer:
    def _redact_value(self, *, key: str, value: object) -> object:
        normalized = str(key).strip().lower()
        should_redact = normalized in _REDACTED_EXACT_KEYS or any(token in normalized for token in _REDACTED_SUBSTRINGS)
        if should_redact:
            return '<redacted>'
        if isinstance(value, dict):
            return {str(child_key): self._redact_value(key=str(child_key), value=child_value) for child_key, child_value in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._redact_value(key=key, value=item) for item in value]
        return value

    def _safe_payload(self, candidate: DecisionCandidate) -> dict:
        payload = candidate.normalized_payload()
        return {str(key): self._redact_value(key=str(key), value=value) for key, value in payload.items()}

    def explain(self, candidate: DecisionCandidate) -> dict:
        return {
            'kind': 'opportunity_explainer',
            'candidate_id': candidate.candidate_id,
            'action_type': candidate.action_type,
            'channel': candidate.channel,
            'objective_score': candidate.objective_score(),
            'reasons': list(candidate.reasons),
            'payload': self._safe_payload(candidate),
        }
