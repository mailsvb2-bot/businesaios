# runtime/executor

Role:
- execute already-approved actions
- coordinate guarded handler invocation
- emit execution-side audit/infra effects

Must NOT contain:
- decision generation
- policy selection
- hidden business decision logic
- bypasses around RuntimeGuard
