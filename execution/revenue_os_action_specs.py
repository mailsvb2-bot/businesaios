from __future__ import annotations

CANON_REVENUE_OS_ACTION_SPECS = True


def build_revenue_os_action_specs():
    from execution.action_contracts import ActionSpec

    return {
        'catalog.revenue.apply_pricing_advisory': ActionSpec(
            action_type='catalog.revenue.apply_pricing_advisory',
            action_class='revenue_advisory',
            executable=False,
            externally_verified=False,
            idempotent=True,
            reversible=True,
            approval_required=True,
            bounded_by_blast_radius=True,
            prod_ready=True,
            notes=(
                'advisory envelope only',
                'must enter DecisionCore path before any execution owner can act',
            ),
        ),
        'catalog.revenue.apply_paywall_advisory': ActionSpec(
            action_type='catalog.revenue.apply_paywall_advisory',
            action_class='revenue_advisory',
            executable=False,
            externally_verified=False,
            idempotent=True,
            reversible=True,
            bounded_by_blast_radius=True,
            prod_ready=True,
            notes=(
                'advisory envelope only',
                'must enter DecisionCore path before any execution owner can act',
            ),
        ),
        'catalog.revenue.apply_subscription_advisory': ActionSpec(
            action_type='catalog.revenue.apply_subscription_advisory',
            action_class='revenue_advisory',
            executable=False,
            externally_verified=False,
            idempotent=True,
            reversible=True,
            bounded_by_blast_radius=True,
            prod_ready=True,
            notes=(
                'advisory envelope only',
                'must enter DecisionCore path before any execution owner can act',
            ),
        ),
    }


__all__ = ['CANON_REVENUE_OS_ACTION_SPECS', 'build_revenue_os_action_specs']
