from __future__ import annotations

CANON_GOAL_FAMILY_CLASSIFIER = True


def _text(value: object) -> str:
    return str(value or '').strip().lower()


class GoalFamilyClassifier:
    def classify(self, goal: object) -> str:
        token = _text(goal)
        if not token:
            return 'default'
        if any(part in token for part in ('revenue', 'sales', 'profit', 'pricing')):
            return 'revenue_growth'
        if any(part in token for part in ('lead', 'pipeline', 'crm', 'prospect')):
            return 'pipeline_growth'
        if any(part in token for part in ('traffic', 'seo', 'search', 'visibility', 'reach')):
            return 'traffic_growth'
        if any(part in token for part in ('retention', 'churn', 'renewal', 'loyal')):
            return 'retention'
        if any(part in token for part in ('ops', 'operations', 'fulfillment', 'delivery')):
            return 'operations'
        return 'default'


__all__ = ['CANON_GOAL_FAMILY_CLASSIFIER', 'GoalFamilyClassifier']
