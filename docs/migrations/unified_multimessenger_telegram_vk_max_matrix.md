# Unified Telegram / VK / MAX migration matrix

## Canonical outcome

BusinessAIOS keeps one messaging domain, one provider approval/write guard, one durable provider queue, one inbound decision owner, one SecretVault, and one sealed HTTP network boundary. Donor code is design evidence only: no donor messenger sender, dispatch worker, connection database, scheduler, retry ledger, or second runtime is copied.

| Capability | Existing BusinessAIOS owner | Decision | Preserved / expanded behavior | Recovery / failure semantics |
| --- | --- | --- | --- | --- |
| Native outbound execution | `runtime.messaging` → BusinessAutonomy provider queue | Strengthen existing path | Telegram, VK and MAX remain selectable channels under one `OutboundMessage` and one policy path | Approval/queue identity stays canonical; no direct native-write bypass |
| VK idempotent send | `ProviderQueueExecutionRuntime` + `ProviderLiveSyncRuntime` | Add provider-safe replay | Stable non-zero `random_id` derives from durable queue job identity | Claim expiry can retry the same VK job without duplicate provider delivery |
| MAX send retry | same provider queue | Separate definitive rejection from ambiguity | Rate-limit and known pre-write rejection retain durable retry | Timeout/5xx after final POST is quarantined as ambiguous; no blind replay |
| MAX pacing | existing BusinessAutonomy distributed CAS + queue `not_before` | Add operational projection | Durable sub-second send spacing without sleeping a worker | Reservation is business-scoped and idempotent by durable job identity |
| VK buttons / callback | canonical `reply_markup` + provider boundary + inbound decoder | Adapt, do not create a second UI model | Inline callback/link buttons translate to VK; oversized layouts repack without losing actions | Beyond real provider capacity fails closed; `message_event` returns to the canonical inbound envelope |
| VK callback acknowledgement | provider webhook ingress + operational responder | Add transport acknowledgement only | Processed `message_event` is acknowledged with `messages.sendMessageEventAnswer` | Business processor runs once; completed replay may retry only the provider acknowledgement |
| Telegram local/private audio | sealed `HttpTransport` + existing Telegram delivery state | Extend existing transport | Local files use multipart; URL/file-id behavior remains JSON-compatible | Disabled-network still blocks the call; queued recovery preserves the same multipart delivery |
| VK audio | provider queue + operational media CAS + sealed HTTP | Add native preparation | `.ogg/.opus` use `audio_message`; other audio uses document upload; final send stays `messages.send` | Approved local bytes are SHA-256-bound before queue admission; prepared attachment survives restart even if the local file is removed; final replay is protected by stable VK `random_id` |
| MAX audio | provider queue + operational media CAS + sealed HTTP | Add two-phase media | Prepare/upload is separated from the final message write | Approved local bytes are SHA-256-bound before queue admission; pre-final crash is retry-safe; prepared token can finish after local-file removal; the final provider boundary remains ambiguous-dead-letter unless definitive non-delivery reopens retry under fencing |
| Provider webhook reconciliation | ProviderAdmin + existing route registry / transport bindings | Add operational self-healing | Telegram setWebhook, VK callback server/settings, MAX subscription are reconciled to the canonical route | Provider application-level rejection fails closed; secret rotation re-runs reconciliation |
| Telegram webhook secret | existing encrypted `SecretVault` | Separate webhook authentication from bot credential | Legacy connection can derive a dedicated webhook secret automatically | Bot token is never reused as webhook shared secret |
| Capability truth | existing provider catalog | Promote only proven capabilities | VK: text/buttons/attachments; MAX: text/attachments; Telegram: existing text/buttons/attachments | MAX buttons remain unadvertised until a real canonical transport exists |

## State, security and ownership constraints

- Pacing and prepared-media records are operational projections in the already-existing BusinessAutonomy SQLite distributed-state database; they are not business truth and are not a second scheduler or delivery ledger.
- The existing provider queue remains the only durable native-send queue. Media helpers cannot import queue, decision, governance, or execution owners.
- Binary uploads are owned only by `runtime/_internal/http_transport.py`; provider helpers do not open `urllib`, `requests`, `httpx`, sockets, or their own HTTP clients.
- Provider base URLs remain owned by `ProviderTransportBindings`; media/reconciliation helpers receive or resolve that existing binding rather than maintaining duplicate endpoint catalogs.
- Provider credentials, webhook secrets and VK confirmation code use the existing encrypted `SecretVault`; prepared media routing tokens use the existing distributed operational CAS and are excluded from public/audit metadata.
- Customer identity and contact projection remains the Unified Customer owner completed in the preceding migration; this slice does not add customer state.
- Inbound webhook replay is still the existing canonical idempotency owner and decision handoff remains `runtime.messaging.inbound_entrypoint`.

## Explicitly not introduced

- no second messenger runtime, sender graph, provider queue, outbox, scheduler, retry ledger, Decision Core, Policy Engine, CRM, Customer store, or idempotency store;
- no donor connection database or donor dispatch worker;
- no `sleep()`-based MAX pacing in a transport worker;
- no blind MAX retry after an ambiguous final provider write;
- no duplicate provider endpoint catalog in media/reconciliation helpers;
- no claim that MAX buttons work before they are implemented in the canonical transport;
- no Email, Sales, Money Cockpit, or later-roadmap migration in this slice.

## Promotion condition

Promotion requires exact ownership/network locks, queue/media/pacing/reconciliation failure tests, provider and messaging regressions, Ruff/compile/diff checks, Canon surface accounting, the complete architecture + business-critical suite, canonical exact-head fast gate, hosted CI and release validation. A green provider call alone is not sufficient evidence.
