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

### Support operator browser journey and access issuance

The original Phase-18 support API had no operator browser UI, so a
real operator could not claim/resolve a case by clicking through the product.
The bounded operator console now lives in the same BusinessAIOS frontend at
`?support_console=1` (not in owner onboarding). It authenticates against
`GET /platform-support/session`, which returns only the authenticated tenant,
business and operator identity after checking `SUPPORT` and explicit
`support_case_manage` scope. It never accepts a caller-supplied tenant or
business selector. Operators can list that business's cases and claim,
release or resolve using revision-checked, idempotent HTTP operations.
Confirmed mutation receipts remain visible if a later queue refresh fails.
The operator credential is held in React memory only: no browser storage,
query-string credentials, owner-session reuse, or support impersonation.

A local administrator, **not** any public endpoint, can provision the
existing canonical persistent API key owner with a short-lived business-bound
SUPPORT key. After setting the same
`BUSINESAIOS_API_KEY_STORE_PATH` and
`API_CONTROL_PLANE_API_KEY_PEPPER` used by the API process, run from a
trusted interactive terminal:

```bash
python -m scripts.support.issue_case_operator_access issue --tenant TENANT_ID --business BUSINESS_ID --operator OPERATOR_ID --ttl-seconds 3600
```

For immediate revocation, run the same module with
`revoke --key-id KEY_ID`. Both commands require an interactive confirmation
and the canonical persistent key store; keys must never be committed,
emailed or printed into CI logs. A browser logout drops its in-memory copy,
but server-side access is revoked only by expiry or key revocation.

**Validation levels must not be conflated:**
- `tests/integration/api/test_phase18_support_full_http_journey.py`
  exercises real FastAPI HTTP, real persistent API-key authentication,
  distinct OWNER/SUPPORT roles, scoped queue isolation, claim/resolve,
  owner visibility and revocation against the canonical memory Event Store.
  It uses the real canonical API security surface and HTTPS test transport;
  the isolated in-memory Event Store is not proof of production PostgreSQL.
- `frontend/e2e/support-operator-journey.spec.js` exercises the operator
  browser UI on the five-browser canonical matrix using explicit network
  response fixtures. These fixtures are **not** a live deployed provider or
  persisted PostgreSQL test.
- Real deployed production and historical donor migration remain separate
  acceptance gates. This slice remains `mapped` until those pass.

### Owner-visible lifecycle proof

The owner support workspace now has a **Показать историю** action on each
case. `GET /business-workspace/support-cases/{case_id}/history` binds the
authenticated owner tenant and business (not a client-provided selector),
replays the same canonical support events that determine the current case
status, and returns revision-ordered timestamps and lifecycle actions
(created → claimed → released → resolved). Its response is capped to the last
50 events by default with a truthful total and truncation flag. It never
publishes operator identifiers, owner tokens, raw event payloads or idempotency
keys. A case from a different business yields 404.

Contract tests exercise the full lifecycle, same-store process restart,
cross-tenant and cross-business denial, limit validation, an unprivileged
support principal denied the owner-only history route, and an HTTPS
OWNER → SUPPORT → OWNER status/history proof through canonical security.
The UI shows loading/failed history on the relevant case only and never
persists the API key.

This is a real new owner-visible *read-only outcome*; it is not audited
platform-wide temporary support access, donor import or production
PostgreSQL parity. Accordingly `support.case_queue` remains `mapped`.

**Not yet complete donor parity:** ClientPlatform's platform-wide case
directory/queue, audited time-boxed support access sessions, operator console,
historical state import/migration and live production journey validation.
For safety, there is **no global case enumeration fallback** and no operator
impersonation of an owner. `support.case_queue` remains **mapped**, not
`implemented` or `parity_proven` until these gaps are closed.

## Program builder: owner-approved lesson handoff and provider acceptance proof

The authenticated owner can now publish a multi-lesson program, enroll a **real
active canonical Customer**, and select an existing active customer identity in a
configured provider. Text and HTTPS-link lessons have a server-generated,
tenant/business-bound **read-only send plan**. No user-supplied recipient or
lesson text is accepted in the plan endpoint; archival/revoked customer
identities are rejected. Unsupported media types stay blocked.

The owner workspace projects that plan into the **existing** Centre действий.
External sending stays under `/actions/execute`, existing DecisionCore,
explicit owner approval, provider queue, and existing provider transport.
`ProgramPublicationRegistry` is not a scheduler, sender or decision engine.

After approval and execution, the owner may reconcile a lesson by approval ID.
The server re-derives the *current canonical* customer/lesson and matches
approved provider payload, canonical Decision Archive, approval fingerprint,
queue job identity, and provider execution-history record (same tenant/business).
Only actual accepted `live_executed` provider results with a resource ID
produce an idempotent `program.lesson_provider_accepted` fact via the **same
canonical Event Store / EventFactLifecycleWriter**. Server-recorded provider
evidence time is reused on retries; status is recovered on restart.

**Important truth boundary:** a provider response acknowledging acceptance
is not proof the recipient device received or displayed a message, and it
does not mean the learner viewed/completed the lesson. The UI and event fact
state `recipient_delivery_confirmed=false` and
`lesson_completion_confirmed=false`. No fake delivery/completion is emitted.
Provider delivery callbacks, canonical inbound acknowledgment/progress, retry
reconciliation, production live-provider proof and legacy donor migration still
must be completed before `commerce.program_builder_delivery` can advance
beyond **mapped** or Phase 18 can be called complete.

Proof: `tests/integration/api/test_phase18_program_lesson_delivery_http.py`
(real authenticated FastAPI + canonical CRM/Event Store with fixture provider);
`tests/integration/api/test_phase18_program_enrollment_canonical_customer.py`
(actual customer and semantic evidence contracts). Fixture provider is *not*
a live deployed Telegram/VK/MAX test.

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
