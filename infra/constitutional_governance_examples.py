from __future__ import annotations

from infra.authority_scopes import AuthorityScope
from infra.constitutional_governance_boot_result import (
    ConstitutionalGovernanceBootResult,
)


def example_constitutional_checks(
    constitutional: ConstitutionalGovernanceBootResult,
) -> dict:
    allowed = constitutional.service.evaluate(
        actor="operator:alice",
        actor_scope=AuthorityScope.OPS,
        action_name="release.promote.prod",
    )
    forbidden = constitutional.service.evaluate(
        actor="operator:bob",
        actor_scope=AuthorityScope.PLATFORM,
        action_name="decision_core.override",
    )

    return {
        "allowed_case": {
            "allowed": allowed.allowed,
            "reasons": list(allowed.reasons),
            "escalation_route": list(allowed.escalation_route),
        },
        "forbidden_case": {
            "allowed": forbidden.allowed,
            "reasons": list(forbidden.reasons),
            "escalation_route": list(forbidden.escalation_route),
        },
    }
