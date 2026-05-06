from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path('.')

BLOCKED_LOW_LEVEL_SECURITY_MODULES = {
    'security.secret_vault_sqlite',
    'security.key_provider_sqlite',
    'security.kms_provider_sqlite',
    'security.governance_journal',
    'security.reencryption_job_store',
    'security.security_drill_schedule_store',
    'security.security_incident_registry',
    'security.security_quarantine_registry',
    'security.token_revocation_store',
    'security.key_rotation_journal',
    'security.security_audit_event_store',
    'security.security_operator_workflow_store',
}
ALLOWED_LOW_LEVEL_SECURITY_IMPORTERS = {
    'security/__init__.py',
    'security/secret_vault.py',
    'security/key_provider.py',
    'security/key_rotation_scheduler.py',
    'security/kms_provider_local_hsm_adapter.py',
    'security/governance_owner_factory.py',
    'security/security_governance_orchestrator.py',
    'security/security_incident_recovery_orchestrator.py',
    'security/security_runtime_summary.py',
    'security/security_pressure_monitor.py',
    'security/security_drill_runtime.py',
    'security/security_rotation_runtime.py',
    'security/security_chaos_mode.py',
    'security/tenant_security_isolation.py',
    'security/reencryption_resume_service.py',
    'security/security_audit_chain.py',
    'security/secret_vault_sqlite.py',
    'adapters/api/fastapi/dependencies.py',
    'runtime/bootstrap/crm_connector_boot.py',
    'crm/providers/common/crm_oauth_token_store.py',
}

ALLOWED_SECURITY_INSTANTIATORS = {
    'bootstrap/ads_wiring.py',
    'interfaces/ads/ports.py',
    'connectors/platform/ads/token_store.py',
    'connectors/platform/ads/vault_env.py',
    'security/secret_vault.py',
    'security/governance_owner_factory.py',
    'security/kms_provider_local_hsm_adapter.py',
}
BLOCKED_INSTANTIATION_PATTERNS = {
    'SecretVault(': 'security owner or explicit boundary adapters must own vault construction',
    'SQLiteKMSProvider(': 'security owner factory must own sqlite kms provider construction',
    'SQLiteGovernanceJournal(': 'security owner factory must own governance journal construction',
    'SQLiteReencryptionJobStore(': 'security owner factory must own reencryption store construction',
    'SQLiteSecurityDrillScheduleStore(': 'security owner factory must own drill schedule store construction',
    'SQLiteSecurityIncidentRegistry(': 'security owner factory must own incident registry construction',
    'SQLiteSecurityQuarantineRegistry(': 'security owner factory must own quarantine registry construction',
}

ALLOWED_LEGACY_SQLITE3_IMPORTERS = {
    'core/security/release_runtime_surface.py',
    'runtime/platform/support/security/__init__.py',
}
LEGACY_SQLITE3_ROOTS = (
    'core/security/',
    'runtime/platform/support/security/',
)


def _py_files() -> list[Path]:
    return [p for p in ROOT.rglob('*.py') if '.venv/' not in p.as_posix()]


def test_repo_wide_low_level_security_modules_do_not_escape_owner_layers() -> None:
    offenders: list[str] = []
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_LOW_LEVEL_SECURITY_IMPORTERS:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in BLOCKED_LOW_LEVEL_SECURITY_MODULES:
                found = True
            elif isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
                if names & BLOCKED_LOW_LEVEL_SECURITY_MODULES:
                    found = True
            if found:
                offenders.append(rel)
                break
    assert not offenders, offenders


def test_repo_wide_low_level_security_stores_are_not_instantiated_outside_owner_or_boundary_layers() -> None:
    offenders: list[str] = []
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_SECURITY_INSTANTIATORS:
            continue
        text = path.read_text(encoding='utf-8')
        for pattern in BLOCKED_INSTANTIATION_PATTERNS:
            if pattern in text:
                offenders.append(rel)
                break
    assert not offenders, offenders


def test_repo_wide_legacy_security_namespaces_do_not_grow_new_sqlite3_dependencies() -> None:
    offenders: list[str] = []
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_LEGACY_SQLITE3_IMPORTERS:
            continue
        if not any(rel.startswith(root) for root in LEGACY_SQLITE3_ROOTS):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(alias.name == 'sqlite3' for alias in node.names):
                offenders.append(rel)
                break
            if isinstance(node, ast.ImportFrom) and node.module == 'sqlite3':
                offenders.append(rel)
                break
    assert not offenders, offenders
