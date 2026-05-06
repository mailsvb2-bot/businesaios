# execution namespace role

Canonical role:
- single owner of generic execution-time primitives and action execution mechanics

Allowed:
- generic action dispatch, action validation, action idempotency, action retry helpers
- reusable execution primitives that can be shared by routing_execution without importing delivery-specific semantics

Forbidden:
- delivery-channel specific policies
- business routing decisions
- duplicating demand delivery orchestration that belongs to routing_execution
