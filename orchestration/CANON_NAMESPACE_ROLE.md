# orchestration namespace role

Canonical role:
- compose higher-level pipelines across already-owned domains

Allowed:
- pipeline composition across opportunity, decision, execution, and feedback stages
- sequencing of already-canonicalized primitives and services
- orchestration-level glue that does not redefine lower-level mechanics

Forbidden:
- owning generic execution primitives or action dispatch mechanics
- re-implementing idempotency, retry, or dispatch cores that belong to execution
- becoming a second owner of domain state or policy truth
