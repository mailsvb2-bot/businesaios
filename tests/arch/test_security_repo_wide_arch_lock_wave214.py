from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path('.')
ALLOWED_SECRET_VAULT_IMPORTERS = {
    'security/__init__.py',
    'security/secret_vault.py',
    'security/secret_vault_sqlite.py',
    'adapters/api/fastapi/dependencies.py',
}
ALLOWED_LOW_LEVEL_SIGNING = {
    'security/request_signing.py',
    'security/request_signature_verifier.py',
    'security/webhook_signature_verifier.py',
    'security/signed_operator_approval.py',
    'security/security_audit_chain.py',
    'security/audit_export_verifier.py',
    'security/external_audit_export_signer.py',
    'security/key_rotation_scheduler.py',
    'security/secret_vault.py',
    'security/integrations/crm_webhook_security_policy.py',
    'runtime/security/signing.py',
    'runtime/security/multiregion_signing.py',
    'entrypoints/api/jwt_policy.py',
    'entrypoints/api/api_key_policy.py',
    'kernel/decision_crypto.py',
    'kernel/decision_signer.py',
    'observability/analytics_export_signature.py',
    'crm/providers/hubspot/hubspot_webhook_signature.py',
    'crm/providers/pipedrive/pipedrive_webhook_signature.py',
    'core/payments/yookassa_webhook.py',
    'runtime/_internal/effects_clients/yookassa_webhook_server.py',
}
ALLOWED_TENANT_SECURITY_DIRECT_READERS = {
    'security/governance_journal.py',
    'security/security_drill_schedule_store.py',
    'security/tenant_security_isolation.py',
    'security/security_runtime_summary.py',
    'security/security_pressure_monitor.py',
    'security/security_drill_runtime.py',
    'security/governance_owner_factory.py',
    'security/reencryption_resume_service.py',
    'security/governance_journal.py',
    'security/reencryption_job_store.py',
}

ALLOWED_EXTERNAL_KMS_IMPORTERS = {
    'security/__init__.py',
    'security/aws_kms_adapter.py',
    'security/gcp_kms_adapter.py',
    'security/vault_transit_kms_adapter.py',
    'security/hardware_hsm_client.py',
    'security/governance_owner_factory.py',
    'security/tenant_security_isolation.py',
    'security/external_adapter_credentials.py',
}
ALLOWED_NOTARY_IMPORTERS = {
    'security/__init__.py',
    'security/security_audit_export_service.py',
    'security/external_audit_notarization.py',
    'security/external_timestamp_authority.py',
    'security/public_ledger_anchor.py',
    'security/governance_owner_factory.py',
    'security/tenant_security_isolation.py',
    'security/external_adapter_credentials.py',
}
ALLOWED_SQLITE3_IN_SECURITY = {
    'security/approval_replay_guard.py',
    'security/governance_journal.py',
    'security/key_rotation_journal.py',
    'security/kms_provider_sqlite.py',
    'security/reencryption_job_store.py',
    'security/reencryption_progress_ledger.py',
    'security/security_audit_chain.py',
    'security/security_audit_event_store.py',
    'security/security_drill_schedule_store.py',
    'security/security_incident_drill_history.py',
    'security/security_incident_registry.py',
    'security/security_operator_workflow_store.py',
    'security/security_quarantine_registry.py',
    'security/secret_vault_sqlite.py',
    'security/signed_operator_approval.py',
    'security/token_revocation_store.py',
}


def _py_files() -> list[Path]:
    return [p for p in ROOT.rglob('*.py') if '.venv/' not in p.as_posix()]


def test_repo_wide_no_low_level_secret_vault_sqlite_imports_escape_owner_layers() -> None:
    offenders: list[str] = []
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_SECRET_VAULT_IMPORTERS:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == 'security.secret_vault_sqlite':
                offenders.append(rel)
                break
    assert not offenders, offenders


def test_repo_wide_no_unapproved_raw_hmac_logic_in_security_related_modules() -> None:
    offenders: list[str] = []
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_LOW_LEVEL_SIGNING:
            continue
        text = path.read_text(encoding='utf-8')
        if 'hmac.new(' in text or 'compare_digest(' in text:
            if any(token in rel for token in ('security/', 'runtime/security/', 'entrypoints/api/', 'kernel/', 'observability/', 'crm/providers/', 'core/payments/')):
                offenders.append(rel)
    assert not offenders, offenders


def test_repo_wide_security_tenant_views_do_not_bypass_tenant_owner_layer() -> None:
    offenders: list[str] = []
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_TENANT_SECURITY_DIRECT_READERS:
            continue
        text = path.read_text(encoding='utf-8')
        if 'SQLiteGovernanceJournal' in text and ('.latest(' in text or '.latest_entity_timeline(' in text):
            offenders.append(rel)
            continue
        if 'SQLiteReencryptionJobStore' in text and ('.list_active()' in text or '.get(' in text):
            offenders.append(rel)
            continue
        if 'SQLiteSecurityDrillScheduleStore' in text and ('.list_enabled()' in text or '.due(' in text):
            offenders.append(rel)
            continue
    assert not offenders, offenders


def test_repo_wide_external_kms_adapters_do_not_escape_security_owner_layers() -> None:
    offenders: list[str] = []
    blocked = {
        'security.aws_kms_adapter',
        'security.gcp_kms_adapter',
        'security.vault_transit_kms_adapter',
        'security.hardware_hsm_client',
    }
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_EXTERNAL_KMS_IMPORTERS:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in blocked:
                offenders.append(rel)
                break
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
                if names & blocked:
                    offenders.append(rel)
                    break
    assert not offenders, offenders


def test_repo_wide_notarization_providers_do_not_escape_audit_owner_layers() -> None:
    offenders: list[str] = []
    blocked = {
        'security.external_audit_notarization',
        'security.external_timestamp_authority',
        'security.public_ledger_anchor',
    }
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_NOTARY_IMPORTERS:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in blocked:
                offenders.append(rel)
                break
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
                if names & blocked:
                    offenders.append(rel)
                    break
    assert not offenders, offenders


def test_repo_wide_security_persistence_ownership_limits_sqlite3_usage() -> None:
    offenders: list[str] = []
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in ALLOWED_SQLITE3_IN_SECURITY:
            continue
        if not rel.startswith('security/'):
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name == 'sqlite3' for alias in node.names):
                    offenders.append(rel)
                    break
            if isinstance(node, ast.ImportFrom) and node.module == 'sqlite3':
                offenders.append(rel)
                break
    assert not offenders, offenders


def test_repo_wide_external_adapter_credential_helpers_do_not_escape_owner_layers() -> None:
    offenders: list[str] = []
    blocked = {'security.external_adapter_credentials'}
    allowed = {
        'security/__init__.py',
        'security/external_adapter_credentials.py',
        'security/tenant_security_isolation.py',
    }
    for path in _py_files():
        rel = path.as_posix()
        if rel.startswith('tests/') or rel in allowed:
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in blocked:
                offenders.append(rel)
                break
            if isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
                if names & blocked:
                    offenders.append(rel)
                    break
    assert not offenders, offenders


def test_repo_wide_security_related_modules_do_not_use_default_external_credentials_literals() -> None:
    offenders: list[str] = []
    allowed = {
        'security/external_adapter_credentials.py',
        'tests/unit/security/test_security_external_adapter_credentials_wave216.py',
        'tests/unit/security/test_security_tenant_external_adapter_binding_wave215.py',
    }
    for path in _py_files():
        rel = path.as_posix()
        if rel in allowed:
            continue
        text = path.read_text(encoding='utf-8')
        if 'default:aws-kms' in text or 'default:gcp-kms' in text or 'default:local-notary' in text or 'default:vault-transit' in text:
            if any(token in rel for token in ('security/', 'runtime/security/', 'entrypoints/api/', 'kernel/', 'observability/', 'crm/providers/', 'core/payments/')):
                offenders.append(rel)
    assert not offenders, offenders
