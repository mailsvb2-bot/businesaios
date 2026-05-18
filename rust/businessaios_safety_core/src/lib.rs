#![forbid(unsafe_code)]

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SafetyVerdict {
    Allow,
    Deny { reason: &'static str },
}

impl SafetyVerdict {
    pub fn is_allow(&self) -> bool {
        matches!(self, SafetyVerdict::Allow)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TenantScope<'a> {
    pub tenant_id: &'a str,
    pub business_id: &'a str,
    pub binding_tenant_id: &'a str,
    pub allow_global_fallback: bool,
}

pub fn validate_tenant_scope(scope: TenantScope<'_>) -> SafetyVerdict {
    if scope.tenant_id.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "tenant_id_required" };
    }
    if scope.business_id.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "business_id_required" };
    }
    if scope.tenant_id == "global" && !scope.allow_global_fallback {
        return SafetyVerdict::Deny { reason: "global_tenant_forbidden" };
    }
    if scope.binding_tenant_id.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "tenant_binding_required" };
    }
    if scope.tenant_id != scope.binding_tenant_id {
        return SafetyVerdict::Deny { reason: "tenant_binding_mismatch" };
    }
    SafetyVerdict::Allow
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MoneyMinor {
    pub amount_minor: i64,
    pub currency: &'static str,
}

pub fn validate_money_amount(value: MoneyMinor) -> SafetyVerdict {
    if value.currency.trim().is_empty() {
        return SafetyVerdict::Deny { reason: "currency_required" };
    }
    if value.amount_minor < 0 {
        return SafetyVerdict::Deny { reason: "negative_amount_forbidden" };
    }
    SafetyVerdict::Allow
}

pub fn validate_budget(estimated: MoneyMinor, approved_limit: MoneyMinor) -> SafetyVerdict {
    if !validate_money_amount(estimated).is_allow() {
        return validate_money_amount(estimated);
    }
    if !validate_money_amount(approved_limit).is_allow() {
        return validate_money_amount(approved_limit);
    }
    if estimated.currency != approved_limit.currency {
        return SafetyVerdict::Deny { reason: "currency_mismatch" };
    }
    if estimated.amount_minor > approved_limit.amount_minor {
        return SafetyVerdict::Deny { reason: "budget_exceeded" };
    }
    SafetyVerdict::Allow
}

pub fn validate_refund(captured: MoneyMinor, refund: MoneyMinor) -> SafetyVerdict {
    if !validate_budget(refund, captured).is_allow() {
        return match validate_budget(refund, captured) {
            SafetyVerdict::Deny { reason: "budget_exceeded" } => SafetyVerdict::Deny { reason: "refund_exceeds_captured" },
            other => other,
        };
    }
    SafetyVerdict::Allow
}

pub fn validate_blast_radius(requested_outbound: u64, approved_limit: u64) -> SafetyVerdict {
    if approved_limit == 0 {
        return SafetyVerdict::Deny { reason: "blast_radius_limit_required" };
    }
    if requested_outbound > approved_limit {
        return SafetyVerdict::Deny { reason: "blast_radius_exceeded" };
    }
    SafetyVerdict::Allow
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IdempotencyState {
    New,
    Reserved,
    Committed,
    FailedRetryable,
    FailedFinal,
}

pub fn validate_idempotency_transition(from: IdempotencyState, to: IdempotencyState) -> SafetyVerdict {
    use IdempotencyState::*;
    match (from, to) {
        (New, Reserved) | (Reserved, Committed) | (Reserved, FailedRetryable) | (Reserved, FailedFinal) => SafetyVerdict::Allow,
        (Committed, Committed) => SafetyVerdict::Deny { reason: "duplicate_committed_execution" },
        (FailedFinal, Reserved) | (FailedFinal, Committed) => SafetyVerdict::Deny { reason: "final_failure_retry_forbidden" },
        _ => SafetyVerdict::Deny { reason: "invalid_idempotency_transition" },
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OutboxState {
    Pending,
    Sent,
    Verified,
    FailedRetryable,
    FailedFinal,
    Cancelled,
}

pub fn validate_outbox_transition(from: OutboxState, to: OutboxState) -> SafetyVerdict {
    use OutboxState::*;
    match (from, to) {
        (Pending, Sent) | (Pending, Cancelled) | (Sent, Verified) | (Sent, FailedRetryable) | (FailedRetryable, Sent) | (FailedRetryable, FailedFinal) => SafetyVerdict::Allow,
        (Verified, Pending) | (Verified, Sent) | (FailedFinal, Sent) | (Cancelled, Sent) => SafetyVerdict::Deny { reason: "terminal_outbox_transition_forbidden" },
        _ => SafetyVerdict::Deny { reason: "invalid_outbox_transition" },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tenant_scope_requires_exact_binding_without_global_fallback() {
        assert_eq!(
            validate_tenant_scope(TenantScope {
                tenant_id: "tenant-a",
                business_id: "site-biz",
                binding_tenant_id: "tenant-a",
                allow_global_fallback: false,
            }),
            SafetyVerdict::Allow,
        );
        assert_eq!(
            validate_tenant_scope(TenantScope {
                tenant_id: "tenant-a",
                business_id: "site-biz",
                binding_tenant_id: "tenant-b",
                allow_global_fallback: false,
            }),
            SafetyVerdict::Deny { reason: "tenant_binding_mismatch" },
        );
        assert_eq!(
            validate_tenant_scope(TenantScope {
                tenant_id: "global",
                business_id: "site-biz",
                binding_tenant_id: "global",
                allow_global_fallback: false,
            }),
            SafetyVerdict::Deny { reason: "global_tenant_forbidden" },
        );
    }

    #[test]
    fn budget_and_money_are_minor_units_and_currency_scoped() {
        assert_eq!(
            validate_budget(
                MoneyMinor { amount_minor: 9_999, currency: "RUB" },
                MoneyMinor { amount_minor: 10_000, currency: "RUB" },
            ),
            SafetyVerdict::Allow,
        );
        assert_eq!(
            validate_budget(
                MoneyMinor { amount_minor: 10_001, currency: "RUB" },
                MoneyMinor { amount_minor: 10_000, currency: "RUB" },
            ),
            SafetyVerdict::Deny { reason: "budget_exceeded" },
        );
        assert_eq!(
            validate_budget(
                MoneyMinor { amount_minor: 10, currency: "USD" },
                MoneyMinor { amount_minor: 10, currency: "RUB" },
            ),
            SafetyVerdict::Deny { reason: "currency_mismatch" },
        );
    }

    #[test]
    fn refund_cannot_exceed_captured() {
        assert_eq!(
            validate_refund(
                MoneyMinor { amount_minor: 5_000, currency: "RUB" },
                MoneyMinor { amount_minor: 5_001, currency: "RUB" },
            ),
            SafetyVerdict::Deny { reason: "refund_exceeds_captured" },
        );
    }

    #[test]
    fn blast_radius_requires_positive_limit_and_blocks_overrun() {
        assert_eq!(validate_blast_radius(1, 0), SafetyVerdict::Deny { reason: "blast_radius_limit_required" });
        assert_eq!(validate_blast_radius(26, 25), SafetyVerdict::Deny { reason: "blast_radius_exceeded" });
        assert_eq!(validate_blast_radius(25, 25), SafetyVerdict::Allow);
    }

    #[test]
    fn idempotency_state_machine_blocks_duplicate_commit() {
        assert_eq!(validate_idempotency_transition(IdempotencyState::New, IdempotencyState::Reserved), SafetyVerdict::Allow);
        assert_eq!(validate_idempotency_transition(IdempotencyState::Reserved, IdempotencyState::Committed), SafetyVerdict::Allow);
        assert_eq!(validate_idempotency_transition(IdempotencyState::Committed, IdempotencyState::Committed), SafetyVerdict::Deny { reason: "duplicate_committed_execution" });
    }

    #[test]
    fn outbox_state_machine_blocks_terminal_rewrites() {
        assert_eq!(validate_outbox_transition(OutboxState::Pending, OutboxState::Sent), SafetyVerdict::Allow);
        assert_eq!(validate_outbox_transition(OutboxState::Sent, OutboxState::Verified), SafetyVerdict::Allow);
        assert_eq!(validate_outbox_transition(OutboxState::Verified, OutboxState::Pending), SafetyVerdict::Deny { reason: "terminal_outbox_transition_forbidden" });
    }
}
