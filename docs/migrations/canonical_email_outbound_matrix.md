# Canonical Email outbound migration matrix

## Canonical outcome

BusinessAIOS keeps one messaging decision path, one provider approval guard, one durable provider queue, one SecretVault and one sealed SMTP network owner. Historical donor code is design evidence only; no donor connection database, dispatch worker, scheduler, CRM or second email runtime is copied.

| Capability | Existing BusinessAIOS owner | Decision | Preserved / expanded behavior | Recovery / failure semantics |
| --- | --- | --- | --- | --- |
| Email message contract | `contracts.email_outbound` | Strengthen one canonical payload | Valid recipient, bounded subject and body; header/control injection rejected | Invalid payload fails before provider I/O |
| SMTP connection settings | provider catalog + `SecretVault` | Replace placeholder provider binding | Host, port, security, sender and optional auth are tenant/business scoped | Missing or malformed settings fail closed |
| Credential verification | provider live probe runtime | Add SMTP NOOP probe | A configured mailbox can be tested without sending a message | Probe failure cannot create delivery evidence |
| Outbound dispatch | BusinessAutonomy provider queue | Route email through existing durable queue | Email shares provider governance/idempotency/audit with other external writes | Direct production SMTP bypass is removed from the canonical dispatcher |
| Human approval | existing provider write guard | Mark email as guarded write | Every live email write requires canonical approval evidence in this slice | Approval is re-evaluated before queue admission and provider execution |
| Provider idempotency | queue job identity + deterministic `Message-ID` | Add provider-side secondary guard | Same durable job produces the same `Message-ID` | Durable queue remains the source of truth; Message-ID is not a second ledger |
| SMTP network I/O | sealed provider outbound transport | Reuse existing network owner | STARTTLS/SSL and optional authentication remain supported | No new `smtplib` owner is introduced |
| Definitive non-delivery | SMTP transport result | Classify explicitly | Authentication/recipient rejection is distinguishable from uncertainty | No false delivery success |
| Pre-send transient failure | provider queue retry policy | Retry only when no write attempt occurred | Connect-stage transient failure may retry under the existing budget | Retry is forbidden once send outcome becomes uncertain |
| Ambiguous final send | provider queue dead-letter semantics | Fail closed | Timeout/transport error after `send_message()` begins is not replayed automatically | Outcome becomes ambiguous/manual-reconciliation work |
| Delivery evidence | provider runtime history/audit | Reuse existing evidence lifecycle | SMTP server acceptance yields stable provider `Message-ID`; it is not claimed as final delivery | Accepted and delivered remain distinct states |
| Compatibility | historical messaging SMTP adapter | Keep temporarily, stop selecting it for scoped production email | Existing implementation/tests remain available during rollout | Remove only after parity and production proof |

## Security and ownership constraints

- SMTP credentials are resolved only from the existing encrypted `SecretVault`; provider/audit responses never contain password/token values.
- Email is a transport capability, not a second Customer, CRM, sales ledger or decision owner.
- The provider queue remains the sole durable external-email work queue.
- The sealed provider outbound transport remains the sole `smtplib` network owner.
- Live writes remain human-approved until a later Sales policy explicitly proves a narrower safe automation rule.
- SMTP acceptance means provider acceptance only; final inbox delivery is not fabricated.
- Reply/inbox ingestion is outside this outbound slice and must use the same Customer/Event Spine owners when added.

## Rollout and rollback

1. Prove contract, SecretVault configuration, live probe and prepared-send behavior without network side effects.
2. Prove approval-required queue admission and exact approval resume.
3. Prove deterministic Message-ID, accepted-vs-delivered evidence, safe pre-send retry and ambiguous-send dead-letter behavior.
4. Route canonical `email` messaging through `email_connector` provider queue.
5. Run architecture/business-critical/multimessenger regressions plus hosted exact-head CI.
6. Keep the historical SMTP adapter as a compatibility surface until production evidence confirms the provider route; rollback is routing-only and must not create a second live owner.

## Explicitly not introduced

- no second Decision Core, Policy Engine, scheduler, outbox, queue, CRM, Customer store or idempotency store;
- no new SMTP networking library or direct socket owner;
- no automatic cold-outreach policy in this slice;
- no inbound email claims;
- no claim of final delivery from SMTP acceptance alone.
