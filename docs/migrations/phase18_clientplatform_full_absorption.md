# Phase 18 — ClientPlatform full absorption matrix

Phase 18 is a product/runtime migration, not a namespace copy.

## Acceptance boundary

BusinessAIOS is the only target product. ClientPlatform is donor evidence only. A slice is not complete until its user-visible behavior is reproduced through an existing BusinessAIOS canonical owner, migration/recovery is proven where state exists, production cutover is complete, duplicate donor runtime is frozen/removed, and the BusinessAIOS path no longer depends on ClientPlatform at runtime.

The completion gate evaluates **all** inventoried slices, including extensions beyond the initial 20-item donor floor. The machine-readable inventory is `config/phase18_clientplatform_absorption_manifest.json`. It pins the inspected donor baseline and carries the donor capability floor into BusinessAIOS without making that donor manifest a source of truth.

## Already mapped before this change

- unified Customer + Timeline → `crm` + Business Event Spine;
- Telegram/VK/MAX messaging → `interfaces.messaging_runtime` and the canonical provider queue;
- Email outbound → canonical messaging/provider runtime;
- funnel intelligence patch v9 → pure logic folded into the existing `advisory` owner, with Decision/Memory/Attribution/Task owners unchanged.

## Event landing — granular status

ClientPlatform's 2026-10-05 event landing release was reviewed as donor evidence. The following code paths are now implemented in BusinessAIOS (without claiming production parity):

- deterministic bounded landing content from event/business facts (hero/audience/outcomes/agenda/speaker/FAQ/CTA, calm/bold/minimal themes);
- canonical Event Store-backed draft create/save and revision-checked publish/unpublish via the existing EventFactLifecycleWriter and idempotency owner;
- authenticated owner UI in `frontend/src/EventLandingWorkspace.jsx`, with editing, server-confirmed operations, revision conflicts and draft preview;
- independent public participant rendering in `frontend/src/PublicEventLanding.jsx`, requesting **published content only** without owner credentials or browser-persisted session;
- explicit data minimization for later AI drafting; registration, customer and provider secrets are excluded from landing content.

Code contracts: `contracts.landing_page.EventLandingContent`, `application.public_site.landing_content`, `application.public_site.event_landing_registry.EventLandingRegistry`.

**Still not production-parity proven:** real browser journey against an actually deployed environment, registration/payment activation, donor data migration and shutdown/rollback evidence. The manifest therefore retains `implemented`, not `parity_proven` or `decommissioned`.

## Event promotion — granular status

Only destination/identity semantics are currently implemented: campaign links retain canonical event identity and target the public event route through the existing Campaign owner.

The donor owner workspace, promotion dashboard, ad-provider binding, registration attribution and omnichannel management flow are not yet parity-proven and remain inventory.

## Current-main donor extensions

The old 20-capability donor manifest is only a floor. Current ClientPlatform main also contains newer product surfaces that Phase 18 must account for, including:

- owner Cockpit/business workspace;
- Sales AI advisory + owner-reviewed draft flow;
- sales workspace;
- event landing full lifecycle;
- event promotion owner flow;
- program builder/delivery/media/progress;
- Yandex Direct owner flow and growth analytics;
- support cases and audited support access;
- backup/DR and recovery evidence.

These are inventoried independently so that a broad capability cannot be declared implemented merely because one sub-contract exists.

## Support cases — first authenticated end-to-end slice

A tenant-scoped support case user journey is now wired to the **existing
Business Event Spine**, not to donor support tables:

1. An authenticated business owner opens **Поддержка** in the canonical owner
   workspace, creates a category/summary case with an idempotency key and
   receives a durable case UUID.
2. The same owner reloads their inbox and sees server-backed status updates.
3. An authenticated tenant/business-bound **SUPPORT** principal with explicit
   `support_case_manage` scope can list that business's queue, claim an open
   case, release their claim, or resolve it. Ownership of a claimed case
   is enforced, and a terminal resolved case cannot be reopened.
4. Repeated commands are handled by the shared ontology fact writer and
   idempotency store; concurrent operations require the same canonical
   state transition token. All events and lookups include authenticated
   tenant **and** business identity.
5. Invalid summaries (including detected credentials), body-injected tenant
   identifiers, stale revisions, duplicate operation payloads and unauthorized
   operator attempts fail closed.

Code: `application.business_autonomy.support_case_registry`,
`adapters.api.fastapi.business_workspace_support_case_routes`,
`frontend/src/SupportCasesWorkspace.jsx`; tests under
`tests/unit/application/test_phase18_support_case_registry.py` and
`tests/unit/adapters/api/fastapi/test_support_case_routes_phase18.py`.

**Not yet complete donor parity:** ClientPlatform's platform-wide case
directory/queue, audited time-boxed support access sessions, operator console,
historical state import/migration and live production journey validation.
For safety, there is **no global case enumeration fallback** and no operator
impersonation of an owner. `support.case_queue` remains **mapped**, not
`implemented` or `parity_proven` until these gaps are closed.

## What is deliberately not copied

- ClientPlatform repositories/tables as parallel persistence;
- ClientPlatform tenancy owner;
- ClientPlatform event/sales/support state machines where BusinessAIOS already has canonical owners;
- ClientPlatform AI workers as a second decision/orchestration brain;
- a second CRM, attribution engine, task engine, campaign engine or messaging runtime.

Transfer means preserving missing product behavior on existing BusinessAIOS owners.

## Gate semantics

`tests/arch/test_phase18_clientplatform_absorption_contract.py` rejects:

- missing donor capability IDs;
- duplicate slice IDs;
- invalid lifecycle states;
- mapped/implemented slices without canonical owner/source of truth;
- parity/cutover claims without evidence;
- cutover/decommission claims while runtime dependency remains.

It intentionally reports Phase 18 incomplete today. Completion can only become true when every required donor capability is decommissioned/obsolete with evidence and no runtime dependency. Current-main extension slices must also be resolved before any product-level claim that ClientPlatform can be shut down without capability loss.
