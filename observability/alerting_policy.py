from __future__ import annotations

"""Technical alert evaluation only.

CANON_COMPAT_SHIM = True

Consumes already-emitted metrics and evaluates technical thresholds.
No business decisions. No second brain.
"""

from observability.alert_rule_contract import AlertComparator, AlertEvaluationInput, AlertMatch, AlertRule
from observability.tenant_metrics_registry import TenantMetricsRegistry


CANON_ALERTING_POLICY = True


class AlertingPolicy:
    def __init__(self, *, metrics_registry: TenantMetricsRegistry) -> None:
        self._metrics_registry = metrics_registry

    def evaluate_rule(self, rule: AlertRule) -> AlertMatch | None:
        rule.validate()
        snapshot = self._metrics_registry.metric_snapshot(
            tenant_id=rule.tenant_id,
            metric_name=rule.metric_name,
            window_seconds=rule.window.seconds,
        )
        if snapshot is None:
            return None

        evaluation = AlertEvaluationInput(
            tenant_id=rule.tenant_id,
            metric_name=rule.metric_name,
            metric_value=float(snapshot['value']),
            sample_count=int(snapshot['sample_count']),
            labels=dict(snapshot.get('labels', {})),
        )
        evaluation.validate()
        if evaluation.sample_count < rule.min_sample_count:
            return None
        if not self._compare(left=float(evaluation.metric_value), comparator=rule.comparator, right=float(rule.threshold)):
            return None
        return AlertMatch(
            tenant_id=rule.tenant_id,
            rule_id=rule.rule_id,
            metric_name=rule.metric_name,
            observed_value=float(evaluation.metric_value),
            threshold=float(rule.threshold),
            severity=rule.severity,
            description=rule.description or f"{rule.metric_name} breached {rule.comparator.value} {rule.threshold}",
            sample_count=int(evaluation.sample_count),
            labels={**dict(rule.labels), **dict(evaluation.labels)},
        )

    def evaluate_all(self, rules: tuple[AlertRule, ...]) -> tuple[AlertMatch, ...]:
        matches: list[AlertMatch] = []
        for rule in rules:
            match = self.evaluate_rule(rule)
            if match is not None:
                matches.append(match)
        return tuple(matches)

    @staticmethod
    def _compare(*, left: float, comparator: AlertComparator, right: float) -> bool:
        if comparator is AlertComparator.GT:
            return left > right
        if comparator is AlertComparator.GTE:
            return left >= right
        if comparator is AlertComparator.LT:
            return left < right
        if comparator is AlertComparator.LTE:
            return left <= right
        if comparator is AlertComparator.EQ:
            return left == right
        raise ValueError(f'unsupported comparator: {comparator}')


__all__ = [
    'AlertingPolicy',
    'CANON_ALERTING_POLICY',
]
