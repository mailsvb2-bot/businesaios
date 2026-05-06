------------------------------ MODULE RuntimeDecisionGate ------------------------------
EXTENDS Naturals, TLC

VARIABLES
    governanceAllowed,
    status,
    executorCalled,
    events,
    metrics,
    traces

Init ==
    /\ governanceAllowed \in BOOLEAN
    /\ status = "pending"
    /\ executorCalled = FALSE
    /\ events = {}
    /\ metrics = {}
    /\ traces = {}

Evaluate ==
    /\ status = "pending"
    /\ status' = IF governanceAllowed THEN "executed" ELSE "blocked"
    /\ executorCalled' = governanceAllowed
    /\ events' = {"decision.evaluated", IF governanceAllowed THEN "decision.executed" ELSE "decision.blocked"}
    /\ metrics' = {"decision.latency_ms", "decision.count"}
    /\ traces' = {"decision.trace"}
    /\ UNCHANGED governanceAllowed

Next == Evaluate

Spec == Init /\ [][Next]_<<governanceAllowed, status, executorCalled, events, metrics, traces>>

NoBypass == status = "executed" => governanceAllowed
FailClosed == status = "blocked" => executorCalled = FALSE
ObservabilityComplete ==
    status # "pending" =>
        /\ "decision.evaluated" \in events
        /\ (status = "executed" => "decision.executed" \in events)
        /\ (status = "blocked" => "decision.blocked" \in events)
        /\ "decision.latency_ms" \in metrics
        /\ "decision.count" \in metrics
        /\ "decision.trace" \in traces
=============================================================================
