"""Evolution layer (slow loop).

This package hosts production-minimal primitives for scheduling and handling
low-frequency "evolution" jobs (e.g., regenerating marketing copy variants).

Design rules:
- No runtime side-effects here.
- Deterministic handlers only.
- Persistence via outbox + event store.
"""
