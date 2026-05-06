# platform_layer.event_store

Role:
- platform storage adapter surface for event persistence
- canonical public import paths live here
- split `*_part*.py` files are internal repository-history fragments only

Rules:
- external code must import public shims/modules, never `*_part1.py` / `*_part2.py`
- sqlite compatibility stays behind `sqlite_event_store.py`
- postgres boundary must fail explicitly, never via missing module imports
