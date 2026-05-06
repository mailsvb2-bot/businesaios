from canon.academic_target_architecture import CANONICAL_LAYER_STACK

MODULE_BOUNDARIES = {
    'app.web': {'allowed_out': {'product', 'contracts', 'observability'}},
    'product': {'allowed_out': {'flow', 'growth.core', 'contracts', 'observability'}},
    'flow': {'allowed_out': {'orchestration', 'execution', 'attribution', 'economics', 'observability'}},
    'orchestration': {'allowed_out': {'core.decision', 'application.decision_input', 'execution', 'observability', 'growth.core'}},
    'core.decision': {'allowed_out': {'core.policies', 'contracts', 'guardrails', 'observability'}},
    'execution': {'allowed_out': {'interfaces', 'contracts', 'guardrails', 'observability'}},
    'interfaces': {'allowed_out': {'interfaces.common', 'contracts', 'shared'}},
}


# Legacy maps remain during migration. The academic target map below defines
# the final owner stack and must be preferred for all new code.
ACADEMIC_TARGET_MODULE_BOUNDARIES = {
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
