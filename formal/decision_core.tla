------------------------------ MODULE DecisionCore ------------------------------
EXTENDS Naturals, Sequences, TLC

VARIABLES
    decisions,
    signed,
    verified,
    committed,
    side_effects

Init ==
    /\ decisions = {}
    /\ signed = {}
    /\ verified = {}
    /\ committed = {}
    /\ side_effects = {}

CreateDecision(d) ==
    /\ d \notin decisions
    /\ decisions' = decisions \cup {d}
    /\ UNCHANGED <<signed, verified, committed, side_effects>>

SignDecision(d) ==
    /\ d \in decisions
    /\ signed' = signed \cup {d}
    /\ UNCHANGED <<decisions, verified, committed, side_effects>>

VerifyDecision(d) ==
    /\ d \in signed
    /\ verified' = verified \cup {d}
    /\ UNCHANGED <<decisions, signed, committed, side_effects>>

CommitDecision(d) ==
    /\ d \in verified
    /\ committed' = committed \cup {d}
    /\ UNCHANGED <<decisions, signed, verified, side_effects>>

ExecuteSideEffect(d) ==
    /\ d \in committed
    /\ side_effects' = side_effects \cup {d}
    /\ UNCHANGED <<decisions, signed, verified, committed>>

Next ==
    \E d :
        CreateDecision(d)
        \/ SignDecision(d)
        \/ VerifyDecision(d)
        \/ CommitDecision(d)
        \/ ExecuteSideEffect(d)

Spec ==
    Init /\ [][Next]_<<decisions, signed, verified, committed, side_effects>>

Invariant ==
    \A d \in side_effects :
        d \in committed
=============================================================================
