"""Entitlements (event-sourced read model).

Normative rules:
- Granting access is an irreversible action -> must go through DecisionCore envelope.
- The durable representation is via proof events (event store).
"""