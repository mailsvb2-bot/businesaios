# Retired: legacy Autopilot onboarding authority

The former Python package in this directory owned a duplicate `Diagnostics` model
and onboarding state machine. It was retired by the Business Discovery BD6
migration on 2026-10-01.

Persisted legacy `autopilot:session.diag` payloads remain readable for migration,
but they are not a source of business truth. The one-way compatibility reader is:

- `application/business_discovery/legacy_onboarding_migration.py`

All migrated business facts are written through
`OwnerBusinessAssertionIngress` into the canonical Evidence / BusinessFact /
State path. Do not restore Python modules in this directory.
