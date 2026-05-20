use crate::SafetyVerdict;

pub fn validate_live_write_requires_approval(live_write: bool, approved: bool) -> SafetyVerdict {
    if live_write && !approved {
        return SafetyVerdict::Deny { reason: "live_write_requires_approval" };
    }
    SafetyVerdict::Allow
}

pub fn validate_paid_action_requires_budget(paid_action: bool, budget_configured: bool) -> SafetyVerdict {
    if paid_action && !budget_configured {
        return SafetyVerdict::Deny { reason: "paid_action_requires_budget" };
    }
    SafetyVerdict::Allow
}

pub fn validate_campaign_launch_requires_budget_and_blast_radius(
    campaign_launch: bool,
    budget_configured: bool,
    blast_radius_configured: bool,
) -> SafetyVerdict {
    if campaign_launch && !budget_configured {
        return SafetyVerdict::Deny { reason: "campaign_launch_requires_budget" };
    }
    if campaign_launch && !blast_radius_configured {
        return SafetyVerdict::Deny { reason: "campaign_launch_requires_blast_radius" };
    }
    SafetyVerdict::Allow
}

pub fn validate_simulation_cannot_write_live_outbox(simulation: bool, writes_live_outbox: bool) -> SafetyVerdict {
    if simulation && writes_live_outbox {
        return SafetyVerdict::Deny { reason: "simulation_live_outbox_forbidden" };
    }
    SafetyVerdict::Allow
}

pub fn validate_operator_override_requires_identity_and_reason(
    override_requested: bool,
    operator_id: &str,
    reason: &str,
) -> SafetyVerdict {
    if !override_requested {
        return SafetyVerdict::Allow;
    }
    if operator_id.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "operator_override_identity_required" };
    }
    if reason.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "operator_override_reason_required" };
    }
    SafetyVerdict::Allow
}

pub fn validate_approval_expiry(requires_approval: bool, approved: bool, approval_expired: bool) -> SafetyVerdict {
    if requires_approval && !approved {
        return SafetyVerdict::Deny { reason: "approval_required" };
    }
    if requires_approval && approval_expired {
        return SafetyVerdict::Deny { reason: "approval_expired" };
    }
    SafetyVerdict::Allow
}

pub fn canonical_scope_key(tenant_id: &str, business_id: &str, operation: &str, idempotency_key: &str) -> String {
    format!("{}:{}:{}:{}", tenant_id.trim(), business_id.trim(), operation.trim(), idempotency_key.trim())
}

pub fn validate_tenant_scope_key(
    tenant_id: &str,
    business_id: &str,
    operation: &str,
    idempotency_key: &str,
    scope_key: &str,
) -> SafetyVerdict {
    if tenant_id.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "tenant_id_required" };
    }
    if business_id.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "business_id_required" };
    }
    if operation.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "operation_required" };
    }
    if idempotency_key.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "idempotency_key_required" };
    }
    if canonical_scope_key(tenant_id, business_id, operation, idempotency_key) != scope_key.trim() {
        return SafetyVerdict::Deny { reason: "tenant_scope_key_mismatch" };
    }
    SafetyVerdict::Allow
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn live_write_requires_approval() {
        assert_eq!(validate_live_write_requires_approval(true, false), SafetyVerdict::Deny { reason: "live_write_requires_approval" });
        assert_eq!(validate_live_write_requires_approval(true, true), SafetyVerdict::Allow);
    }

    #[test]
    fn simulation_cannot_write_live_outbox() {
        assert_eq!(validate_simulation_cannot_write_live_outbox(true, true), SafetyVerdict::Deny { reason: "simulation_live_outbox_forbidden" });
    }

    #[test]
    fn scope_key_is_deterministic() {
        assert_eq!(canonical_scope_key("tenant", "biz", "op", "idem"), "tenant:biz:op:idem");
        assert_eq!(
            validate_tenant_scope_key("tenant", "biz", "op", "idem", "tenant:biz:op:idem"),
            SafetyVerdict::Allow,
        );
    }
}
