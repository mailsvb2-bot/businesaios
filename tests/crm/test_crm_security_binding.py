from security.integrations.crm_audit_redaction_policy import CrmAuditRedactionPolicy


def test_security_redacts_tokens():
    payload = CrmAuditRedactionPolicy().redact({'access_token': 'secret'})
    assert payload['access_token'] == '***REDACTED***'
