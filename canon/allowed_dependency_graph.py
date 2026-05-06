from canon.academic_target_architecture import CANONICAL_LAYER_STACK

ALLOWED_DEPENDENCY_GRAPH = {
    'app.web': {'product', 'contracts', 'observability'},
    'product': {'flow', 'growth.core', 'contracts', 'observability'},
    'flow': {'orchestration', 'execution', 'attribution', 'economics', 'observability'},
    'orchestration': {'core.decision', 'application.decision_input', 'execution', 'observability', 'growth.core'},
    'core.decision': {'contracts', 'application.decision_input', 'core.policies', 'guardrails', 'observability'},
    'execution': {'contracts', 'interfaces', 'guardrails', 'observability'},
    'interfaces': {'interfaces.common', 'contracts', 'shared'},
}


# Legacy maps remain during migration. The academic target map below defines
# the final owner stack and must be preferred for all new code.
ACADEMIC_TARGET_DEPENDENCY_GRAPH = {
    "kernel": set(),
    "domain": {"kernel"},
    "application": {"kernel", "domain", "ports", "governance", "security", "observability", "config"},
    "ports": {"kernel"},
    "adapters": {"kernel", "ports", "observability", "security", "config"},
    "entrypoints": {"application", "kernel", "observability", "security"},
    "bootstrap": set(CANONICAL_LAYER_STACK) - {"bootstrap"},
    "observability": {"kernel", "config"},
    "governance": {"kernel", "domain", "config", "observability"},
    "security": {"kernel", "config", "observability"},
    "config": set(),
}
