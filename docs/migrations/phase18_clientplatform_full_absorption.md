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

## First new Phase 18 slice: event landing

ClientPlatform's 2026-10-05 event landing release was reviewed as donor evidence. The transferable product semantics are:

- deterministic safe landing draft from event/business facts;
- bounded hero/audience/outcomes/agenda/speaker/FAQ/CTA schema;
- calm/bold/minimal presentation theme;
- explicit data minimization for any later AI drafting;
- registration/customer/provider secrets are not part of landing content.

These semantics are now represented by `contracts.landing_page.EventLandingContent` and `application.public_site.landing_content`.

Not copied:

- ClientPlatform repositories/tables;
- ClientPlatform tenancy owner;
- ClientPlatform event runtime;
- ClientPlatform AI provider client;
- a second registration form, CRM, attribution engine or persistence layer.

The next step for this slice is wiring draft/publish/preview lifecycle to the existing canonical Event/Artifact/Task/Execution owners instead of transplanting ClientPlatform's repository state machine.

## Gate semantics

`tests/arch/test_phase18_clientplatform_absorption_contract.py` rejects:

- missing donor capability IDs;
- duplicate slice IDs;
- invalid lifecycle states;
- mapped/implemented slices without canonical owner/source of truth;
- parity/cutover claims without evidence;
- cutover/decommission claims while runtime dependency remains.

It intentionally reports Phase 18 incomplete today. Completion can only become true when every required donor capability is decommissioned/obsolete with evidence and no runtime dependency.
