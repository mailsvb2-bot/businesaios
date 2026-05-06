# CANON MIGRATION DEPRECATION REMEDIATION V1

Цель:
оформлять canonical migrations и deprecations как управляемый переход, а не как бесконечный "временный" слой.

## Типовые исправления
- добавить migration entry в `docs/CANON_MIGRATION_DEPRECATION_REGISTRY_DATA_V1.yaml`
- назначить owner
- добавить target_date
- указать `from_paths` и `to_paths`
- закрыть или перевести open migration в blocked/active осознанно

## Главный смысл

Migration registry нужен не для оправдания legacy,
а для его управляемого устранения.
