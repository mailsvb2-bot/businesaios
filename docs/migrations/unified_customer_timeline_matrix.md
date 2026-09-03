# Unified Customer + Timeline migration matrix

## Canonical outcome

BusinessAIOS keeps one customer semantic contract, one CRM owner surface, one Business Event Spine chronology truth, one existing encrypted SecretVault for recoverable customer PII, and one read-only customer timeline projection. Donor implementations are used only as design evidence; no donor database, repository, runtime, or mutable timeline store is introduced.

| Capability | Existing BusinessAIOS owner | Decision | Preserved / adapted behavior | Data / compatibility | Security and failure semantics | Regression proof | Rollout / rollback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Customer semantic identity | `contracts/customer.py` | Strengthen existing owner | Customer is explicitly tenant + business scoped; archive is explicit | Existing import path remains canonical | Missing/invalid scope fails closed through contract/store boundaries | semantic-owner architecture lock | Revert contract extension only before persisted customer facts exist |
| Channel identity | `contracts/customer.py` + `crm.CustomerRegistry` | Add identity under existing CRM owner | Multiple channel identities may belong to one customer; email/phone normalization; no automatic cross-customer merge | Identity membership/channel/digest are persisted as Business Facts; raw subject/name/handle stay only in the existing encrypted SecretVault | Same identity in same business cannot bind to two customers; concurrent claim uses canonical idempotency owner | conflict, concurrency, cross-tenant/business tests | Disable ingress wiring; facts remain valid append-only history |
| Customer PII / routing material | existing `security.SecretVault` | Reuse security owner, not CRM storage | Returned CustomerIdentity is hydrated only after vault integrity/digest verification | Raw subject, username and display name are absent from EventStore facts; vault ref is tenant + business scoped | Missing, disabled, malformed or digest-mismatched vault data fails closed | raw-PII absence, encrypted-vault hydration and revocation tests | Vault revocation removes usable routing material without rewriting append-only chronology |
| Customer creation / lookup | `crm.CustomerRegistry` | New operation under canonical CRM root | Idempotent ensure, explicit attach, archive | Derived from `business_fact.v1`; no second mutable registry | Atomic identity claim before first customer fact; replay returns original customer | repeat-ingress and single-truth tests | Stop new writes; projection can still read existing facts |
| Contact observation | `crm.CustomerRegistry` | Add canonical fact projection | Repeated transport event is idempotent; first/last contact derived | Deterministic fact identity preserves replay compatibility | Fact append also uses canonical idempotency owner | duplicate-contact and concurrent-ingress tests | Stop contact projection without deleting history |
| Customer timeline | `crm.CustomerTimelineProjector` | Read model only | Strict chronology; customer facts plus explicit business/customer-linked events | No timeline table or writable timeline source | Cross-business events excluded; malformed money fails closed | read-only, isolation, chronology tests | Remove projector with no data migration |
| Provider messaging ingress | existing provider webhook service | Enrich existing ingress | Verified accepted messaging ingress projects customer before downstream decision handoff | Uses runtime canonical event store supplied by API composition | Invalid signature/replay never creates customer; archived identities cannot reactivate | provider ingress integration test | Omit canonical event-store dependency to return to previous behavior |
| CRM public surface | `crm/__init__.py` | Extend existing root | Expose registry/projector through current package owner | Existing CRM exports untouched | No new alternate CRM package | owner/import regression tests | Remove two lazy exports |

## Explicitly not introduced

- no customer database or customer repository beside the canonical EventStore;
- no raw customer PII in EventStore facts; recoverable routing/profile PII uses the already-canonical encrypted SecretVault;
- no writable timeline store;
- no second CRM package or service graph;
- no new scheduler, queue, outbox, decision engine, policy engine, or messaging runtime;
- no automatic identity merge based on weak similarity;
- no tenant-to-business inference.

## Promotion condition

The capability is promotable only when architecture ownership tests, customer single-truth tests, provider-ingress regression, Ruff/compile/diff locks, canonical fast gate, architecture/business-critical suite, hosted CI, and release validation all pass on the exact pull-request head.
