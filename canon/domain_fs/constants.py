from __future__ import annotations

DOMAIN_FILE_SYSTEM_VERSION = "DFS-V1"
CANON_DOMAIN_MARKER = "__canon_domain__.py"

STRATEGIC_DOMAIN_NAMES: tuple[str, ...] = (
    "world_model",
    "economics",
    "experiments",
    "knowledge",
    "product",
    "governance",
    "finance",
    "simulation",
    "learning_loop",
    "human_governance",
)

REQUIRED_ROOT_FILES: tuple[str, ...] = (
    "contracts.py",
    "types.py",
    "errors.py",
    "service.py",
    "guard.py",
)

OPTIONAL_ROOT_FILES: tuple[str, ...] = (
    "__init__.py",
    "__canon_domain__.py",
    "enums.py",
    "ids.py",
    "policy.py",
)

ALLOWED_SUBDIRS: tuple[str, ...] = (
    "contracts",
    "readers",
    "writers",
    "builders",
    "evaluators",
    "explainers",
    "guards",
    "policies",
    "repositories",
    "projections",
    "serializers",
    "mappers",
    "events",
)

FORBIDDEN_ROLE_NAMES: tuple[str, ...] = (
    "brain",
    "manager",
    "orchestrator",
    "commander",
    "director",
    "master",
    "supervisor",
    "processor",
)

FORBIDDEN_FILENAME_STEMS: tuple[str, ...] = FORBIDDEN_ROLE_NAMES + ("engine",)

FORBIDDEN_SECOND_BRAIN_PATTERNS: tuple[str, ...] = (
    "DecisionRoute(",
    "EXPECTED_ISSUER_ID",
    "issue_decision(",
    "issue_action(",
    "choose_strategy(",
    "choose_action(",
    "optimize_strategy(",
    "apply_campaign(",
    "apply_pricing(",
    "execute_action(",
    "runtime.handlers.ads_apply",
    "runtime.handlers.pricing_select",
    "runtime.handlers.growth_propose",
    "runtime.handlers.ai_ceo_plan",
)

ROOT_FILE_LINE_LIMITS: dict[str, int] = {
    "service.py": 220,
    "policy.py": 180,
    "guard.py": 180,
    "contracts.py": 220,
    "types.py": 220,
    "errors.py": 140,
    "enums.py": 160,
    "ids.py": 160,
}

THIN_HANDLER_LINE_LIMIT = 180
BOOT_WIRING_LINE_LIMIT = 180

# Transitional canon debt zones: keep runtime stable while domains migrate
# into strict DFS-V1 layout.
LEGACY_RELAXED_DOMAINS: tuple[str, ...] = (
    "economics",
    "finance",
    "product",
)

# Transitional per-domain root-file allowlist.
# Use this to gradually exit LEGACY_RELAXED_DOMAINS without breaking runtime.
DOMAIN_OPTIONAL_ROOT_FILES: dict[str, tuple[str, ...]] = {
    "knowledge": (
        "contracts_legacy.py",
    ),
    "human_governance": (
        "contracts_deps.py",
        "contracts_policy.py",
        "contracts_readers.py",
        "contracts_repositories.py",
        "contracts_writers.py",
    ),
}