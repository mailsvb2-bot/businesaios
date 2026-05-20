use businessaios_safety_core::{
    validate_blast_radius, validate_budget, validate_idempotency_transition, validate_outbox_transition,
    validate_refund, validate_tenant_scope, IdempotencyState, MoneyMinor, OutboxState, SafetyVerdict,
    TenantScope,
};
use proptest::prelude::*;

proptest! {
    #[test]
    fn budget_denies_when_estimate_exceeds_limit(estimate in 0i64..1_000_000, limit in 0i64..1_000_000) {
        let verdict = validate_budget(
            MoneyMinor { amount_minor: estimate, currency: "RUB" },
            MoneyMinor { amount_minor: limit, currency: "RUB" },
        );
        if estimate > limit {
            prop_assert_eq!(verdict, SafetyVerdict::Deny { reason: "budget_exceeded" });
        } else {
            prop_assert_eq!(verdict, SafetyVerdict::Allow);
        }
    }

    #[test]
    fn refund_never_exceeds_captured(captured in 0i64..1_000_000, refund in 0i64..1_000_000) {
        let verdict = validate_refund(
            MoneyMinor { amount_minor: captured, currency: "RUB" },
            MoneyMinor { amount_minor: refund, currency: "RUB" },
        );
        if refund > captured {
            prop_assert_eq!(verdict, SafetyVerdict::Deny { reason: "refund_exceeds_captured" });
        } else {
            prop_assert_eq!(verdict, SafetyVerdict::Allow);
        }
    }

    #[test]
    fn blast_radius_denies_over_limit(requested in 0u64..1_000_000, limit in 0u64..1_000_000) {
        let verdict = validate_blast_radius(requested, limit);
        if limit == 0 {
            prop_assert_eq!(verdict, SafetyVerdict::Deny { reason: "blast_radius_limit_required" });
        } else if requested > limit {
            prop_assert_eq!(verdict, SafetyVerdict::Deny { reason: "blast_radius_exceeded" });
        } else {
            prop_assert_eq!(verdict, SafetyVerdict::Allow);
        }
    }

    #[test]
    fn cross_tenant_binding_is_always_denied(a in "[a-z]{1,16}", b in "[a-z]{1,16}") {
        prop_assume!(a != b);
        let verdict = validate_tenant_scope(TenantScope {
            tenant_id: &a,
            business_id: "site",
            binding_tenant_id: &b,
            allow_global_fallback: false,
        });
        prop_assert_eq!(verdict, SafetyVerdict::Deny { reason: "tenant_binding_mismatch" });
    }
}

#[test]
fn idempotency_duplicate_commit_is_always_denied() {
    assert_eq!(
        validate_idempotency_transition(IdempotencyState::Committed, IdempotencyState::Committed),
        SafetyVerdict::Deny { reason: "duplicate_committed_execution" },
    );
}

#[test]
fn terminal_outbox_transitions_are_denied() {
    for (from, to) in [
        (OutboxState::Verified, OutboxState::Pending),
        (OutboxState::Verified, OutboxState::Sent),
        (OutboxState::FailedFinal, OutboxState::Sent),
        (OutboxState::Cancelled, OutboxState::Sent),
    ] {
        assert_eq!(
            validate_outbox_transition(from, to),
            SafetyVerdict::Deny { reason: "terminal_outbox_transition_forbidden" },
        );
    }
}
