# CANON MIGRATION DEPRECATION REGISTRY V1

Цель:
сделать все canonical migrations и deprecations явными, ограниченными и проверяемыми.

## Главный закон

Если legacy-to-canon переход не внесён в migration/deprecation registry,
то это не миграция, а бесконтрольный архитектурный дрейф.

## Что считается migration/deprecation item

Любой управляемый переход, например:
- `*_legacy.py` должен быть выведен из active flow
- hotspot name должен быть переименован в canonical role
- old runtime/boot entrypoint должен быть заменён canonical entrypoint
- direct cross-domain coupling должен быть заменён contract boundary
- old decision-space narrowing pattern должен быть переписан в score/observe/explain form
