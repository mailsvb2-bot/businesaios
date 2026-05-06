# Historical note: patch pipeline

This repository does not treat patch files as a canonical source of truth.

The source of truth is the checked-in project tree itself:
- domain code
- runtime wiring
- tests
- canonical architecture documents

If a patch artifact appears in the repository, it is only a temporary migration aid.
It must not become a required installation or delivery path.
It must not define runtime behavior.
It must not replace normal code integration into the project tree.
