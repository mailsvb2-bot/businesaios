# CANON_BOOT_RUNTIME_REGISTRY_REMEDIATION_V1

Цель:
чинить boot/runtime registry drift канонично, без появления второго мозга.

## Правило remediation

Если файл является public boot entrypoint:
- добавить `CANON_BOOT_WIRING_ONLY = True`
- оставить только wiring / registration / binding / assembly semantics

Если файл является public runtime handler:
- добавить `CANON_THIN_HANDLER = True`
- оставить parse / validate / map / call service / return DTO

## Важная staged-оговорка

Сначала audit накатывается на public entrypoints.
Внутренние helper / builder / private files подтягиваются дальше отдельными проходами.
