"""
BUSINESAIOS SUPER CANON ENGINE

This module defines mandatory engineering rules of the project.

All AI systems, chats, developers and scripts must follow these rules
before modifying any part of the codebase.

Violation of these rules is considered architecture drift.
"""

CANON_VERSION = 'V21'

CANON_RULES = {
    'mandatory_reading': True,
    'no_functionality_loss': True,
    'single_decision_core': True,
    'single_execution_contract': True,
    'single_dataflow': True,
    'single_infrastructure_layer': True,
    'no_second_brain': True,
    'no_hidden_business_logic': True,
    'no_fake_integrations': True,
    'no_duplicate_infrastructure': True,
    'no_synonym_entities': True,
    'no_god_modules': True,
    'no_silent_failures': True,
    'anti_drift_tests_required': True,
    'repo_certification_required': True,
    'world_model_single_canonical_path': True,
    'world_model_port_required': True,
    'world_model_pinning_required': True,
    'world_model_replay_required': True,
    'world_model_boot_integrity_required': True,
    'world_model_ci_enforcement_required': True,
    'world_model_no_legacy_bypass': True,
    'declarative_audit_forbidden': True,
    'deep_multilayer_verification_required': True,
    'verify_to_last_file_required': True,
    'direct_project_fixes_only': True,
    'systemic_canonical_fix_only': True,
    'fix_immediately_when_found': True,
    'domain_file_system_canon_required': True,
    'new_feature_must_be_visible_in_admin': True,
    'thin_handlers_required': True,
    'boot_wiring_only_required': True,
    'simplification_constitution_required': True,
    'full_functionality_preservation_required': True,
    'no_false_fallback_truth': True,
    'no_parasitic_glue_logic': True,
    'no_duplicate_guard_logic': True,
    'no_synonymous_logic_paths': True,
    'radical_simplification_requires_proof': True,
    'public_contract_regression_forbidden': True,
    'false_improvement_forbidden': True,
}


FORBIDDEN_ARCHITECTURE_DEFECTS = [
    'duplicated infrastructure',
    'god module',
    'second brain',
    'hidden business logic',
    'multiple dataflows',
    'inconsistent metrics',
    'synonym entities',
    'scattered configs',
    'fake integrations',
    'mixed async/sync',
    'decorative tests',
    'code duplication',
    'empty production files',
    'fake observability',
    'world-model bypass',
    'world-model drift',
    'unpinned decision execution',
    'unreplayable decision path',
    'boot-time world-model integrity hole',
    'parasitic glue logic',
    'duplicate guard logic',
    'synonymous logic paths',
    'false fallback truth',
    'public contract regression',
    'false improvement',
]


def verify_canon_loaded() -> bool:
    """Ensures the canon rules are loaded before modifications."""
    required_true = (
        'mandatory_reading',
        'single_decision_core',
        'no_second_brain',
        'world_model_single_canonical_path',
        'world_model_pinning_required',
        'world_model_boot_integrity_required',
        'declarative_audit_forbidden',
        'deep_multilayer_verification_required',
        'verify_to_last_file_required',
        'direct_project_fixes_only',
        'systemic_canonical_fix_only',
        'fix_immediately_when_found',
        'domain_file_system_canon_required',
        'new_feature_must_be_visible_in_admin',
        'thin_handlers_required',
        'boot_wiring_only_required',
        'simplification_constitution_required',
        'full_functionality_preservation_required',
        'no_false_fallback_truth',
        'no_parasitic_glue_logic',
        'no_duplicate_guard_logic',
        'no_synonymous_logic_paths',
        'radical_simplification_requires_proof',
        'public_contract_regression_forbidden',
        'false_improvement_forbidden',
    )
    for key in required_true:
        if not CANON_RULES.get(key):
            raise RuntimeError(f'Canon rules not enforced: {key}')
    return True
