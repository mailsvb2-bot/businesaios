use businessaios_safety_core::{
    validate_blast_radius, validate_budget, validate_idempotency_transition, validate_outbox_transition,
    validate_refund, validate_tenant_scope, IdempotencyState, MoneyMinor, OutboxState, SafetyVerdict,
    TenantScope,
};

#[test]
fn budget_denies_when_estimate_exceeds_limit_across_representative_ranges() {
    for estimate in [0, 1, 10, 10_000, 999_999] {
        for limit in [0, 1, 10, 10_000, 999_999] {
            let verdict = validate_budget(
                MoneyMinor { amount_minor: estimate, currency: "RUB" },
                MoneyMinor { amount_minor: limit, currency: "RUB" },
            );
            if estimate > limit {
                assert_eq!(verdict, SafetyVerdict::Deny { reason: "budget_exceeded" });
            } else {
                assert_eq!(verdict, SafetyVerdict::Allow);
            }
        }
    }
}

#[test]
fn refund_never_exceeds_captured_across_representative_ranges() {
    for captured in [0, 1, 10, 10_000, 999_999] {
        for refund in [0, 1, 10, 10_000, 999_999] {
            let verdict = validate_refund(
                MoneyMinor { amount_minor: captured, currency: "RUB" },
                MoneyMinor { amount_minor: refund, currency: "RUB" },
            );
            if refund > captured {
                assert_eq!(verdict, SafetyVerdict::Deny { reason: "refund_exceeds_captured" });
            } else {
                assert_eq!(verdict, SafetyVerdict::Allow);
            }
        }
    }
}

#[test]
fn blast_radius_denies_over_limit_across_representative_ranges() {
    for requested in [0, 1, 10, 25, 999_999] {
        for limit in [0, 1, 10, 25, 999_999] {
            let verdict = validate_blast_radius(requested, limit);
            if limit == 0 {
                assert_eq!(verdict, SafetyVerdict::Deny { reason: "blast_radius_limit_required" });
            } else if requested > limit {
                assert_eq!(verdict, SafetyVerdict::Deny { reason: "blast_radius_exceeded" });
            } else {
                assert_eq!(verdict, SafetyVerdict::Allow);
            }
        }
    }
}

#[test]
fn cross_tenant_binding_is_always_denied_for_representative_tenants() {
    for (a, b) in [("a", "b"), ("tenant-a", "tenant-b"), ("site", "other"), ("global", "tenant-a")] {
        let verdict = validate_tenant_scope(TenantScope {
            tenant_id: a,
            business_id: "site",
            binding_tenant_id: b,
            allow_global_fallback: false,
        });
        if a == "global" {
            assert_eq!(verdict, SafetyVerdict::Deny { reason: "global_tenant_forbidden" });
        } else {
            assert_eq!(verdict, SafetyVerdict::Deny { reason: "tenant_binding_mismatch" });
        }
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
