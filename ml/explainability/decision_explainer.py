from kernel.decision_result import DecisionResult


class DecisionExplainer:
    def explain(self, result: DecisionResult) -> dict:
        candidate = result.candidate
        return {
            'kind': 'decision_explainer',
            'approved': result.approved,
            'action_type': getattr(candidate, 'action_type', None),
            'channel': getattr(candidate, 'channel', None),
            'reason_codes': [item.code for item in result.reasons],
            'decision_id': getattr(result.trace, 'decision_id', ''),
            'request_id': getattr(result.trace, 'request_id', ''),
            'has_executable_action': result.executable_action is not None,
        }
