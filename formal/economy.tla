VARIABLES
    users,
    balance,
    price,
    revenue

Init ==
    /\ users = {}
    /\ balance = [u \in {} |-> 0]
    /\ price = 100
    /\ revenue = 0

NoNegative ==
    \A u \in DOMAIN balance : balance[u] >= 0

RevenueConsistent ==
    revenue >= 0

PriceSafe ==
    price >= 0 /\ price <= 100000
