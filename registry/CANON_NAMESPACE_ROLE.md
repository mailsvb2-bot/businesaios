# registry namespace role

Canonical role:
- thin compatibility namespace for small named registries that rely on the shared registry core
- local semantic wrappers around the shared registry primitives

Allowed:
- tiny registry adapters
- stable import surfaces
- explicit compatibility markers

Forbidden:
- second storage implementation for generic registry behavior
- hidden policy truth or domain decisions
- duplicate in-memory registry engines parallel to shared/registry.py
