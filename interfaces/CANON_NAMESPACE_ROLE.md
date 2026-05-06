# interfaces namespace role

This package is the **boundary adapter and connector surface**.

Allowed here:
- external platform connectors
- boundary adapters
- web/API delivery surfaces
- messaging and integration entrypoints
- protocol translation around canonical contracts and schemas

Must NOT contain:
- a second domain contract truth beside `contracts/`
- core decision ownership
- hidden business policy truth
- schema-only semantic ownership
- duplicate sovereign runtime logic from `core/` or `runtime/`

Rule:
- `interfaces/` translates between the outside world and canonical internal layers.
- `contracts/` owns semantic shapes.
- `schemas/` owns validation and serialization helpers.
