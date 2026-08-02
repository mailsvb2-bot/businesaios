# Randomized live canary with real business outcomes

The live canary runtime is disabled by default and fails closed when enabled
with an invalid configuration. It is intended for one tenant, one candidate
policy and a narrow allowlist of reversible actions.

## Required environment

```text
LIVE_CANARY_ENABLED=true
LIVE_CANARY_EXPERIMENT_ID=metro-followup-2026-08
LIVE_CANARY_ASSIGNMENT_SECRET=<at least 32 random bytes>
LIVE_CANARY_CANDIDATE_PCT=1
LIVE_CANARY_TENANTS=<one tenant id>
LIVE_CANARY_ALLOWED_ACTIONS=send_preapproved_message@v1
LIVE_CANARY_OUTCOME_EVENTS=booking_confirmed@v1,payment_succeeded
```

Assignment is HMAC-based over experiment, tenant and subject. The raw subject
identifier is never written to experiment evidence. Every assignment, actual
execution proof and actual business outcome is linked by `decision_id`.

## Safe rollout

1. Register the candidate at 0% and verify telemetry.
2. Collect at least 1,000 shadow decisions and 100 real production outcomes.
3. Enable a 1% live canary for a single allowlisted action.
4. Run `LiveCanaryWatchdog` as a supervised service. A critical violation,
   cost breach, error-rate breach, complaint breach or sample-ratio mismatch
   returns the candidate to 0%.
5. Expand beyond 1% only after `LiveCanaryGuard` returns `promote` from actual,
   non-counterfactual business outcomes.

Payments, refunds, price changes, deletion and permission changes must not be
placed in the first canary allowlist.

## Integration contract

At the decision boundary call `LiveCanaryCoordinator.assign`. Execute either
the control or candidate policy according to the returned arm. Before a
candidate action reaches an executor, call `assert_candidate_action_allowed`.
After execution, call `record_execution` with the provider proof event and
external evidence reference. When a booking, payment or other governed outcome
arrives, call `record_outcome` with the same `decision_id`.

Promotion uses sample-ratio validation, actual conversion, a confidence-bound
non-inferiority check, cost per outcome, complaint rate, error rate and critical
violations. Missing or non-finite evidence never promotes a candidate.
