"""BUSINESAIOS canon package."""

from .authority_registry import CANONICAL_AUTHORITY_OWNERS, CanonAuthority
from .canon_ai_enforcer import EnforcerReport, Violation, run_enforcer
from .canon_change_policy import (
    CHANGE_POLICY_FORBIDDEN_PATTERNS,
    CHANGE_POLICY_RULES,
    CHANGE_POLICY_VERSION,
    verify_change_policy_loaded,
)
from .canon_critical_error_search import CRITICAL_ERROR_TYPES, error_types, required_first_pass, required_second_pass
from .canon_protocol import WORK_PROTOCOL, get_protocol
from .canon_repo_cleaner import JUNK_EXTENSIONS, JUNK_PATTERNS, is_junk, scan_repo
from .canon_report_requirements import REPORT_REQUIREMENTS, required_report_sections
from .canon_rules import CANON_RULES, CANON_VERSION, FORBIDDEN_ARCHITECTURE_DEFECTS, verify_canon_loaded
from .canon_simplification_manifest import CANON_SIMPLIFICATION_MANIFEST, iter_manifest
from .canon_world_model_integrity import (
    REQUIRED_WORLD_MODEL_CANON_FILES,
    REQUIRED_WORLD_MODEL_CANON_STRINGS,
    WORLD_MODEL_CANON_VERSION,
    scan_world_model_canon_contract,
)
from .canon_world_model_integrity import (
    findings_as_dicts as world_model_findings_as_dicts,
)
from .domain_fs import (
    ALLOWED_SUBDIRS,
    BOOT_WIRING_LINE_LIMIT,
    CANON_DOMAIN_MARKER,
    DOMAIN_FILE_SYSTEM_VERSION,
    FORBIDDEN_FILENAME_STEMS,
    FORBIDDEN_ROLE_NAMES,
    REQUIRED_ROOT_FILES,
    STRATEGIC_DOMAIN_NAMES,
    THIN_HANDLER_LINE_LIMIT,
    scan_boot_wiring_only,
    scan_canon_domain_file_system,
    scan_thin_runtime_handlers,
)
from .domain_fs import (
    findings_as_dicts as domain_fs_findings_as_dicts,
)
from .module_manifests import DEFAULT_CANON_MODULE_MANIFESTS, CanonModuleManifest, CanonModuleRole
from .route_spec import CANONICAL_EXECUTION_PATH, CANONICAL_ROUTE_OWNERS
from .sealed_effect_policy import EFFECT_LITERAL_MARKERS, FORBIDDEN_EXTERNAL_EFFECT_LIBRARIES, SEALED_EFFECT_PREFIXES
from .simplification_constitution import (
    ALL_CANON_INVARIANTS,
    CANON_SIMPLIFICATION_CONSTITUTION_VERSION,
    SIMPLIFICATION_RULES,
    SimplificationClass,
    SimplificationIntent,
    SimplificationVerdict,
)
from .simplification_contracts import (
    LayerAssessment,
    SimplificationEvaluation,
    SimplificationProposal,
    assert_canon_simplification,
    classify_layer_for_simplification,
    detect_parasitic_glue,
    evaluate_simplification,
    must_fail_closed_when_scope_missing,
)
from .trace_contracts import CANONICAL_TRACE_STAGES

# Preserve the original package-level helper name for existing world-model users.
findings_as_dicts = world_model_findings_as_dicts
canon_domain_findings_as_dicts = domain_fs_findings_as_dicts

__all__ = [
    "ALLOWED_SUBDIRS",
    "BOOT_WIRING_LINE_LIMIT",
    "CANON_DOMAIN_MARKER",
    "CANON_RULES",
    "CANON_VERSION",
    "CHANGE_POLICY_FORBIDDEN_PATTERNS",
    "CHANGE_POLICY_RULES",
    "CHANGE_POLICY_VERSION",
    "CRITICAL_ERROR_TYPES",
    "DOMAIN_FILE_SYSTEM_VERSION",
    "EnforcerReport",
    "FORBIDDEN_ARCHITECTURE_DEFECTS",
    "FORBIDDEN_FILENAME_STEMS",
    "FORBIDDEN_ROLE_NAMES",
    "JUNK_EXTENSIONS",
    "JUNK_PATTERNS",
    "REPORT_REQUIREMENTS",
    "REQUIRED_ROOT_FILES",
    "REQUIRED_WORLD_MODEL_CANON_FILES",
    "REQUIRED_WORLD_MODEL_CANON_STRINGS",
    "STRATEGIC_DOMAIN_NAMES",
    "THIN_HANDLER_LINE_LIMIT",
    "Violation",
    "WORK_PROTOCOL",
    "WORLD_MODEL_CANON_VERSION",
    "canon_domain_findings_as_dicts",
    "error_types",
    "findings_as_dicts",
    "get_protocol",
    "is_junk",
    "required_first_pass",
    "required_report_sections",
    "required_second_pass",
    "run_architecture_checks",
    "run_canon_checks",
    "run_operational_canon_checks",
    "run_enforcer",
    "scan_boot_wiring_only",
    "scan_canon_domain_file_system",
    "scan_repo",
    "scan_thin_runtime_handlers",
    "scan_world_model_canon_contract",
    "verify_canon_loaded",
    "verify_change_policy_loaded",
    "ALL_CANON_INVARIANTS",
    "CANON_SIMPLIFICATION_CONSTITUTION_VERSION",
    "CANON_SIMPLIFICATION_MANIFEST",
    "LayerAssessment",
    "SIMPLIFICATION_RULES",
    "SimplificationClass",
    "SimplificationEvaluation",
    "SimplificationIntent",
    "SimplificationProposal",
    "SimplificationVerdict",
    "assert_canon_simplification",
    "classify_layer_for_simplification",
    "detect_parasitic_glue",
    "evaluate_simplification",
    "iter_manifest",
    "must_fail_closed_when_scope_missing",
    "CANONICAL_AUTHORITY_OWNERS",
    "CanonAuthority",
    "DEFAULT_CANON_MODULE_MANIFESTS",
    "CanonModuleManifest",
    "CanonModuleRole",
    "CANONICAL_EXECUTION_PATH",
    "CANONICAL_ROUTE_OWNERS",
    "EFFECT_LITERAL_MARKERS",
    "FORBIDDEN_EXTERNAL_EFFECT_LIBRARIES",
    "SEALED_EFFECT_PREFIXES",
    "CANONICAL_TRACE_STAGES",
]



def run_architecture_checks() -> bool:
    from .canon_architecture_guard import run_architecture_checks as _impl
    return _impl()


def run_canon_checks(*args, **kwargs):
    from tools.canon_audit.checks import run_canon_checks as _impl
    return _impl(*args, **kwargs)


def run_operational_canon_checks(*args, **kwargs):
    from tools.canon_audit.checks import run_operational_canon_checks as _impl
    return _impl(*args, **kwargs)
