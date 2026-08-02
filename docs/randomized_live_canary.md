# Randomized live canary with real business outcomes

The live canary runtime is disabled by default and fails closed when enabled
with an invalid configuration. It is intended for one tenant, one candidate
policy, one explicit business purpose and a narrow allowlist of reversible
actions.

## Required environment

```text
LIVE_CANARY_ENABLED=true
LIVE_CANARY_EXPERIMENT_ID=metro-followup-2026-08-stage-1
LIVE_CANARY_ASSIGNMENT_SECRET=<at least 32 random bytes>
LIVE_CANARY_CANDIDATE_PCT=1
LIVE_CANARY_MAX_CANDIDATE_PCT=1
LIVE_CANARY_TENANTS=<one tenant id>
LIVE_CANARY_PURPOSES=live_canary
LIVE_CANARY_ELIGIBILITY_STATE_KEY=live_canary_eligible
LIVE_CANARY_ALLOWED_ACTIONS=send_message@v1
LIVE_CANARY_OUTCOME_EVENTS=booking_confirmed@v1,payment_succeeded
LIVE_CANARY_OUTCOME_WINDOW_SECONDS=259200
LIVE_CANARY_OUTCOME_POLL_SECONDS=5
LIVE_CANARY_MIN_DURATION_SECONDS=259200
LIVE_CANARY_MAX_ACTIONS_PER_SUBJECT_24H=1
```

Only states with an allowed `purpose` and an explicit
`live_canary_eligible=true` flag enter the experiment. The business adapter is
responsible for setting that flag only after consent, frequency-cap and domain
eligibility checks. Absence of the flag always routes to control.

The candidate policy must itself be restricted to approved message content.
Free-form generation, payment capture, refunds, price changes, deletions and
permission changes are not suitable for the first canary.

Assignment is HMAC-based over experiment, tenant and subject. The raw subject
identifier is never written to experiment evidence. Candidate action allowlists
are applied only after assignment; control actions are not excluded merely
because they differ from the candidate action.

## Evidence contract

Every assignment, actual execution proof and actual business outcome is linked
by `decision_id`.

A successful execution is accepted only when the canonical action proof from
`ACTION_PROOF_EVENT` already exists, reports `ok=true`, and is not a stub.
A business outcome is accepted only when a separate non-stub source event of
the configured outcome type exists for the same decision. Revenue and value are
derived from that source event rather than trusted from caller input.

Assignments are evaluated only after their full outcome window has matured.
Newer assignments remain visible to safety guardrails but cannot contribute to
a promotion decision.

## Safe rollout

1. Register the candidate at 0% and verify shadow telemetry.
2. Collect at least 1,000 shadow decisions and 100 real production outcomes.
3. Enable a 1% live canary for one tenant, one purpose and one allowlisted
   action.
4. Run `LiveCanaryWatchdog` as a supervised service. A critical violation,
   cost breach, global or per-subject frequency breach, error-rate breach,
   complaint breach or sample-ratio mismatch returns the candidate to 0%.
5. Expand beyond 1% only after `LiveCanaryGuard` returns `promote` from mature,
   actual, non-counterfactual outcomes.

Each rollout stage is evidence-isolated by its recorded percentage. Before
requesting a larger stage, raise `LIVE_CANARY_MAX_CANDIDATE_PCT` to the intended
ceiling while leaving the current rollout untouched. The promotion gate checks
the completed current stage, then the deployment effect changes the registry.
For operational clarity, a new experiment ID per stage is still recommended.

## Integration contract

Canonical boot attaches `LiveCanaryCoordinator` and starts the supervised `LiveCanaryOutcomeObserver` when the feature is enabled. The observer polls the shared event ledger at `LIVE_CANARY_OUTCOME_POLL_SECONDS`, and its lifecycle is owned by the live-canary wiring.
The decision boundary verifies purpose, eligibility, tenant and the stable
assignment bucket. After the provider emits an execution proof, call
`record_execution`. After a booking, payment or other governed source event is
stored, call `record_outcome` with the same `decision_id`.

Promotion uses sample-ratio validation, mature conversion, a confidence-bound
non-inferiority check, cost per outcome, complaint rate, error rate and critical
violations. Missing, conflicting, stub or non-finite evidence never promotes a
candidate.
