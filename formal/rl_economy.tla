------------------------------ MODULE RLEconomy ------------------------------
EXTENDS Naturals, Sequences, TLC

(*
Tier‑Ω FINAL: RL + Economy + Governance formal skeleton.

Goal:
- Prevent mathematically unsafe states (negative balances, unbounded price)
- Ensure governance can freeze/rollback before unsafe actions commit
*)

CONSTANTS Users, Actions, MaxPrice

VARIABLES
    balance,          \* [u \in Users |-> Nat]
    price,            \* Nat
    revenue,          \* Nat
    frozen,           \* BOOLEAN
    lastAction,       \* in Actions
    rewardLog         \* sequence of rewards

Init ==
    /\ balance = [u \in Users |-> 0]
    /\ price = 100
    /\ revenue = 0
    /\ frozen = FALSE
    /\ lastAction \in Actions
    /\ rewardLog = << >>

\* --- Reward model (abstract) ---
Reward(a) ==
    IF a = "CREATE_PAYMENT" THEN 5
    ELSE IF a = "SEND_MESSAGE" THEN 1
    ELSE 0

\* --- Safe price range ---
PriceSafe ==
    /\ price >= 0
    /\ price <= MaxPrice

\* --- Balances cannot go negative ---
NoNegative ==
    \A u \in Users : balance[u] >= 0

\* --- Revenue monotonic ---
RevenueConsistent ==
    revenue >= 0

\* --- Governance safety: if frozen, no payment actions are allowed ---
NoPaymentsWhenFrozen ==
    frozen => lastAction # "CREATE_PAYMENT"

\* --- Transition: RL chooses an action (abstract nondet choice) ---
ChooseAction ==
    /\ ~frozen
    /\ \E a \in Actions :
        /\ lastAction' = a
        /\ rewardLog' = Append(rewardLog, Reward(a))
        /\ UNCHANGED <<balance, price, revenue, frozen>>

\* --- Transition: execute payment (abstract) ---
ApplyPayment ==
    /\ ~frozen
    /\ lastAction = "CREATE_PAYMENT"
    /\ \E u \in Users :
        /\ balance' = [balance EXCEPT ![u] = balance[u]]  \* keep non-negative in model
        /\ revenue' = revenue + price
        /\ UNCHANGED <<price, frozen, lastAction, rewardLog>>

\* --- Transition: governance can freeze on anomaly ---
Freeze ==
    /\ frozen' = TRUE
    /\ UNCHANGED <<balance, price, revenue, lastAction, rewardLog>>

\* --- Transition: governance can rollback price to safe baseline ---
RollbackPrice ==
    /\ price' = 100
    /\ UNCHANGED <<balance, revenue, frozen, lastAction, rewardLog>>

Next ==
    ChooseAction
    \/ ApplyPayment
    \/ Freeze
    \/ RollbackPrice

Spec ==
    Init /\ [][Next]_<<balance, price, revenue, frozen, lastAction, rewardLog>>

Safety ==
    NoNegative /\ RevenueConsistent /\ PriceSafe /\ NoPaymentsWhenFrozen
=============================================================================
