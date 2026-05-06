# routing_execution namespace role

Canonical role:
- owner of demand lead delivery orchestration and channel-specific delivery semantics

Allowed:
- channel selection, delivery validation, delivery outcome normalization, business/customer delivery notifications
- thin reuse of generic execution primitives from execution

Forbidden:
- re-implementing generic execution primitives when execution already owns them
- becoming a second generic execution framework for unrelated action execution
- bypassing canonical delivery contracts
