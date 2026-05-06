------------------------------ MODULE Governance ------------------------------
EXTENDS Naturals, Sequences, TLC

VARIABLES
    metrics,
    decision

Init ==
    /\ metrics = [revenue_drop |-> 0, anomaly_score |-> 0]
    /\ decision = "ok"

Evaluate ==
    IF metrics["revenue_drop"] > 0.5 THEN decision' = "rollback"
    ELSE IF metrics["anomaly_score"] > 0.9 THEN decision' = "freeze"
    ELSE decision' = "ok"

Next ==
    Evaluate

Spec ==
    Init /\ [][Next]_<<metrics, decision>>

Safety ==
    decision \in {"ok", "rollback", "freeze"}
=============================================================================
