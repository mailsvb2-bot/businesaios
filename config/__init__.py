from __future__ import annotations
"""Canonical config namespace with lazy public exports."""
from importlib import import_module
from typing import Any
CANON_CONFIG_PUBLIC_API = True
CANON_CONFIG_PACKAGE_OWNER = True
_DIRECT_EXPORTS = {
    'CANON_CONFIG_AUDIT': ('config.config_audit', 'CANON_CONFIG_AUDIT'), 'ConfigAuditEvent': ('config.config_audit', 'ConfigAuditEvent'), 'PersistentConfigAuditLog': ('config.config_audit', 'PersistentConfigAuditLog'),
    'CANON_CONFIG_VERSIONING': ('config.config_versioning', 'CANON_CONFIG_VERSIONING'), 'ConfigVersion': ('config.config_versioning', 'ConfigVersion'), 'ConfigVersioning': ('config.config_versioning', 'ConfigVersioning'),
    'CANON_ENVIRONMENT_MATRIX': ('config.environment_matrix', 'CANON_ENVIRONMENT_MATRIX'), 'EnvironmentMatrix': ('config.environment_matrix', 'EnvironmentMatrix'), 'EnvironmentMatrixRow': ('config.environment_matrix', 'EnvironmentMatrixRow'), 'normalize_environment_name': ('config.environment_matrix', 'normalize_environment_name'),
    'CANON_CONFIG_FEATURE_FLAGS': ('config.feature_flags', 'CANON_CONFIG_FEATURE_FLAGS'), 'ConfigFeatureFlagResolver': ('config.feature_flags', 'ConfigFeatureFlagResolver'), 'FeatureFlagSnapshot': ('config.feature_flags', 'FeatureFlagSnapshot'),
    'CANON_POLICY_CONFIG_STORE': ('config.policy_config_store', 'CANON_POLICY_CONFIG_STORE'), 'InMemoryPolicyConfigStore': ('config.policy_config_store', 'InMemoryPolicyConfigStore'), 'PersistentPolicyConfigStore': ('config.policy_config_store', 'PersistentPolicyConfigStore'), 'PolicyConfigSnapshot': ('config.policy_config_store', 'PolicyConfigSnapshot'),
    'CANON_RUNTIME_CONFIG_STORE': ('config.runtime_config_store', 'CANON_RUNTIME_CONFIG_STORE'), 'InMemoryRuntimeConfigStore': ('config.runtime_config_store', 'InMemoryRuntimeConfigStore'), 'PersistentRuntimeConfigStore': ('config.runtime_config_store', 'PersistentRuntimeConfigStore'), 'RuntimeConfigSnapshot': ('config.runtime_config_store', 'RuntimeConfigSnapshot'),
    'CANON_TENANT_CONFIG_STORE': ('config.tenant_config_store', 'CANON_TENANT_CONFIG_STORE'), 'InMemoryTenantConfigStore': ('config.tenant_config_store', 'InMemoryTenantConfigStore'), 'PersistentTenantConfigStore': ('config.tenant_config_store', 'PersistentTenantConfigStore'), 'TenantConfigSnapshot': ('config.tenant_config_store', 'TenantConfigSnapshot'),
    'CANON_SECRETS_RESOLUTION_POLICY': ('config.secrets_resolution_policy', 'CANON_SECRETS_RESOLUTION_POLICY'), 'SecretResolutionRequest': ('config.secrets_resolution_policy', 'SecretResolutionRequest'), 'SecretResolver': ('config.secrets_resolution_policy', 'SecretResolver'), 'SecretsResolutionPolicy': ('config.secrets_resolution_policy', 'SecretsResolutionPolicy'),
    'CANONICAL_FLOW': ('config.system_config', 'CANONICAL_FLOW'), 'CANONICAL_OBJECTIVE_NAME': ('config.system_config', 'CANONICAL_OBJECTIVE_NAME'), 'ConfigSection': ('config.system_config', 'ConfigSection'), 'OptimizationObjective': ('config.system_config', 'OptimizationObjective'), 'RuntimeLimits': ('config.system_config', 'RuntimeLimits'), 'SystemConfig': ('config.system_config', 'SystemConfig'),
    'CANON_CONFIG_VALIDATION': ('config.validation', 'CANON_CONFIG_VALIDATION'), 'validate_app_settings': ('config.validation', 'validate_app_settings'), 'validate_http_settings': ('config.validation', 'validate_http_settings'), 'validate_runtime_environment': ('config.validation', 'validate_runtime_environment'), 'validate_system_config': ('config.validation', 'validate_system_config'), 'validate_telegram_settings': ('config.validation', 'validate_telegram_settings'),
    'CANON_RUNTIME_ENVIRONMENT': ('config.runtime_environment', 'CANON_RUNTIME_ENVIRONMENT'), 'RuntimeEnvironment': ('config.runtime_environment', 'RuntimeEnvironment'), 'RuntimeFlags': ('config.runtime_environment', 'RuntimeFlags'), 'load_app_settings': ('config.runtime_environment', 'load_app_settings'), 'load_http_settings': ('config.runtime_environment', 'load_http_settings'), 'load_runtime_environment': ('config.runtime_environment', 'load_runtime_environment'), 'load_runtime_flags': ('config.runtime_environment', 'load_runtime_flags'), 'load_telegram_settings': ('config.runtime_environment', 'load_telegram_settings'), 'read_setting': ('config.runtime_environment', 'read_setting'),
}

def __getattr__(name: str) -> Any:
    if name in _DIRECT_EXPORTS:
        module_name, attr_name = _DIRECT_EXPORTS[name]
        module = import_module(module_name)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    catalog = import_module('config.catalog')
    try:
        value = getattr(catalog, name)
    except AttributeError as exc:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}') from exc
    globals()[name] = value
    return value
__all__ = sorted(set(_DIRECT_EXPORTS) | {'CANON_CONFIG_PUBLIC_API', 'CANON_CONFIG_PACKAGE_OWNER'})
