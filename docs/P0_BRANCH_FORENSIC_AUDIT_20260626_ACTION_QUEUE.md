# P0 recovered branch action queue

This file intentionally tracks only the actionable extraction queue from the preserved backup branch.

Source branch:

- `backup/p0-release-readiness-hardening-20260626T174221Z`
- SHA: `05ad107ce37fb10a3bc6dfd3415920bc8e528600`

## Queue

1. Audit and extract support import-door replacement slices one domain at a time.
2. Start with governance import surfaces only if focused import tests can prove safety.
3. Then evaluate safety runtime contracts for canonical RuntimeGuard integration.
4. Then evaluate events/idempotency support, but only if it strengthens existing outbox/ledger flow.

## Do not extract

- bulk support platform;
- generated artifacts;
- release manifest churn;
- broad workflows;
- stale conftest or gitignore changes;
- cosmetic wrappers without removing dynamic import-door dependency.
