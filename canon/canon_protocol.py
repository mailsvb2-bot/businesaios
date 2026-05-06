"""
BUSINESAIOS SUPER CANON WORK PROTOCOL

Every AI system or developer must follow this procedure
before completing a modification task.
"""

WORK_PROTOCOL = [
    'Read the canonical source of truth: docs/SYSTEM_TZ_CANONICAL.md',
    'Read the Architecture Canon',
    'Declarative audit is forbidden',
    'Only deep multilayer verification to the last file is allowed',
    'Only direct project fixes are allowed; reports without code changes are forbidden',
    'Every found error must be fixed immediately with a systemic canonical change',
    'Verify no functionality loss',
    'Analyze the entire affected subsystem',
    'Find at least 10 critical errors',
    'Fix all of them canonically',
    'Verify AI modules',
    'Search for second brain patterns',
    'Search for alternative execution paths',
    'Search for double logic / divergence',
    'Search for architectural risks',
    'Verify one canonical world-model path into DecisionCore',
    'Verify DecisionCore depends only on DecisionWorldModelPort',
    'Verify world-model pinning / replay / audit are preserved',
    'Verify boot self-check / CI integrity are preserved',
    'Fix everything without hacks',
    'Then find 15 more critical errors',
    'Fix them canonically',
    'Verify architecture consistency',
    'Verify boot modules remain wiring-only',
    'Verify thin handlers remain thin',
    'Verify canon domain file-system rules',
    'Every new feature must also be added to the admin plane with status/risk visibility',
    'Verify execution contract',
    'Verify unified dataflow',
    'Verify infrastructure ownership',
    'Clean repository artifacts',
    'Build final clean archive',
    'Write full technical report',
    'Write full project capability report',
]


def get_protocol():
    return WORK_PROTOCOL