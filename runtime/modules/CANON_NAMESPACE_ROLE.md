# runtime/modules

Role:
- runtime wiring metadata only
- module registration and service exposure descriptors
- must not implement decision logic
- must not expose raw concrete DecisionCore as a public runtime service name

Canonical rule:
- runtime should expose `decision_gateway` instead of a raw `decision_core` service key
