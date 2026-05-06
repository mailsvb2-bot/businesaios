# runtime execution boundary

The runtime layer is the ONLY place where irreversible side-effects may occur.

Allowed responsibilities:
- guarded execution of already-approved actions
- validation of execution payloads
- audit / observability emission

Must NOT:
- generate new decisions
- reinterpret policies
- run hidden business logic
- bypass RuntimeGuard
