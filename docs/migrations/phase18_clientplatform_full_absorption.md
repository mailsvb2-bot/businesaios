# Phase 18 — ClientPlatform full absorption matrix

Phase 18 is a product/runtime migration, not a namespace copy.

## Acceptance boundary

BusinessAIOS is the only target product. ClientPlatform is donor evidence only. A slice is not complete until its user-visible behavior is reproduced through an existing BusinessAIOS canonical owner, migration/recovery is proven where state exists, production cutover is complete, duplicate donor runtime is frozen/removed, and the BusinessAIOS path no longer depends on ClientPlatform at runtime.

The machine-readable inventory is `config/phase18_clientplatform_absorption_manifest.json`. It pins the inspected donor baseline and carries the donor capability floor into BusinessAIOS without making that donor manifest a source of truth.

## Already mapped before this change

- unified Customer + Timeline → `crm` + Business Event Spine;
- Telegram/VK/MAX messaging → `interfaces.messaging_runtime` and the canonical provider queue;
- Email outbound → canonical messaging/provider runtime;
- funnel intelligence patch v9 → pure logic folded into the existing `advisory` owner, with Decision/Memory/Attribution/Task owners unchanged.

## Event landing — granular status

ClientPlatform's 2026-10-05 event landing release was reviewed as donor evidence. Only the presentation contract is currently implemented in BusinessAIOS:

- deterministic safe landing content from event/business facts;
- bounded hero/audience/outcomes/agenda/speaker/FAQ/CTA schema;
- calm/bold/minimal presentation theme;
- explicit data minimization for later AI drafting;
- registration/customer/provider secrets are excluded from landing content.

These semantics are represented by `contracts.landing_page.EventLandingContent` and `application.public_site.landing_content`.

The broader donor lifecycle is **not** marked implemented. Draft persistence, revision ordering, preview, publish/unpublish and owner-facing workflow remain inventory until they are wired through existing BusinessAIOS Event/Artifact/Task/Execution owners and proved end-to-end.

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
