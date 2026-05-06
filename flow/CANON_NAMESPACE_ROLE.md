# flow namespace role

Purpose:
- compose stage-to-stage handoff surfaces
- preserve readable end-to-end flow sequencing
- stay thin and orchestration-adjacent

Allowed:
- sequencing of already-owned pipeline or bridge stages
- thin end-to-end composition wrappers
- readability helpers for canonical closed-loop paths

Forbidden:
- owning generic execution primitives
- owning action dispatch mechanics
- owning retry or idempotency engines
- becoming a second source of execution business logic
