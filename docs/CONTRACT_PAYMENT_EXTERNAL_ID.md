# Contract: payment_created.payload.external_id

This repo treats `payment_created.payload.external_id` as a **strict, mandatory contract**.

## Definition

When the system emits a `payment_created` event, it MUST include:

```json
{
  "event_type": "payment_created",
  "user_id": "<canonical user id>",
  "payload": {
    "external_id": "<provider payment id>",
    "provider": "yookassa",
    "status": "<optional provider status>"
  }
}
```

## Why this is mandatory

The webhook ingress and reconciliation pipeline rely on a deterministic join:

`webhook.object.id` (provider payment id) → `payment_created.payload.external_id` → `payment_created.user_id`

This is the only canonical way to map an external payment notification back to a user **without introducing a second brain / secondary database**.

## If you do NOT enforce this

- Webhook events become "orphans" (`user_id=unknown`).
- Reconcile jobs cannot be targeted to a user reliably.
- You get non-deterministic outcomes under load (duplicate terminal events, missed entitlements).
- Any attempt to fix mapping "later" usually creates a second contour (bad) or hidden heuristics (also bad).

## Validation

The runtime validates that `external_id` is present and matches a conservative safe format.
Invalid webhooks are rejected with 400 and recorded as proof events.
