# Phase 18: canonical consolidation (13 October 2026)

**Integration policy:** This branch is the single candidate integration tree. Do not independently merge PRs #478, #479, #480, #481, #482, or the large donor PR #472. The final production decision must use exact-HEAD CI and real user-journey evidence. This document records provenance; it is not a release claim.

## Exact ancestry and selection

- Main base: `688b9036828de59dd9dd6c23c65c01c1dda2c7e0`.
- Commercial code: #478 -> #479 -> #481; #481 is a strict descendant of #479, itself a descendant of #478. Preserve one canonical Lead/Customer/Program/Order/Invoice/PSP evidence route. No alternative CRM, ledger, payment authority or new decision brain.
- SQLite + CI: select #480 as canonical, because it probes the idle reaper read-only using a **closed connection**, safely retries only the pre-transaction BEGIN IMMEDIATE under contention, and shards the entire business-critical test suite. #482 contains a competing reaper implementation; do not overwrite #480 with it. Preserve its independent fail-closed shard regression test, adjusted for the selected 16-files/shard bound.
- #472: never merge all 368 commits/141 files as a unit. Its source inventory is retained as `config/phase18_clientplatform_absorption_manifest.json`, with claim provenance preserved and all statuses capped at `mapped` until independent production proof. Missing evidence files are explicitly recorded rather than invented. The architecture manifest lock is retained.

## Authority and truth boundaries

The browser owner issues requests against authenticated, tenant/business-scoped routes. Lead/Customer/Program registries and canonical invoice/order stores own state. Checkout binding is **not settlement**. PSP status is not merchant settlement without authoritative reconciliation. Provider acceptance is **not recipient delivery**. Program enrollment is **not learner completion**. Execution must follow the existing approved Policy/ActionIntent/Execution owners; no second execution pathway, donor runtime import, invented money state, or hidden user data transfer.

## Explicit release blockers

- Real PSP merchant integration and signed webhook + independent settlement/reversal evidence.
- Production durable order backend and PostgreSQL/restart/idempotency tests under multi-worker load.
- Live provider fulfillment, entitlement, provider delivery acknowledgment, outcome and attribution propagation.
- Browser E2E on integrated exact HEAD with authenticated owner journey; no green-check inference from unit tests alone.
- The unreconciled donor slices captured in the conservative registry; no ClientPlatform retirement yet.
- Exact HEAD full/architectural CI and queue soak after integration; stale green parent PR checks are insufficient.

## Traceability

GitHub PRs: [#478](https://github.com/mailsvb2-bot/businesaios/pull/478), [#479](https://github.com/mailsvb2-bot/businesaios/pull/479), [#480](https://github.com/mailsvb2-bot/businesaios/pull/480), [#481](https://github.com/mailsvb2-bot/businesaios/pull/481), [#482](https://github.com/mailsvb2-bot/businesaios/pull/482), [#472](https://github.com/mailsvb2-bot/businesaios/pull/472).

No historical donor code or donor table is silently imported by this integration.
