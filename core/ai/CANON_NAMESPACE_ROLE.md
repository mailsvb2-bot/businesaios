Canonical owner: DecisionCore-facing policy object selection and in-process AI policy access.

Allowed:
- wiring-time registration of concrete policy objects
- active-policy object lookup for DecisionCore / selector paths
- compatibility facade for rollout-aware policy object resolution

Forbidden:
- becoming a second rollout-state truth separate from core/policies
- executing irreversible effects
- bypassing RuntimeExecutor governance
