# schemas namespace role

This package is the **validation and serialization schema surface**.

Allowed here:
- schema helpers
- serialization adapters
- validation-oriented shapes
- transport-safe representations derived from canonical contracts

Must NOT contain:
- connector integrations
- business orchestration
- a second domain contract truth beside `contracts/`
- provider runtime adapters
- hidden policy logic

Rule:
- `schemas/` refines or validates data for transport and storage.
- `contracts/` remains the **canonical semantic source**.
- `interfaces/` remains the **boundary adapter and connector layer**.
