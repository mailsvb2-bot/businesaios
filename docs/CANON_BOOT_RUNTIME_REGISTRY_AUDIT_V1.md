# CANON_BOOT_RUNTIME_REGISTRY_AUDIT_V1

Цель:
зафиксировать канонический статус boot и runtime entrypoints.

## Главный закон

Если public boot/runtime entrypoint существует в проекте, он обязан быть явно канонизирован.

В staged-режиме audit применяется к:
- public boot entrypoints внутри `runtime/boot/*`, которые реально содержат wiring functions
- public runtime handlers внутри `runtime/handlers/*`, которые реально содержат `handle_*`

## Канонические boot entrypoints

Public boot entrypoints должны:
- лежать внутри `runtime/boot/*`
- иметь `CANON_BOOT_WIRING_ONLY = True`
- выполнять wiring / registration / binding / assembly
- не быть marker-only shell

## Канонические runtime handlers

Public runtime handlers должны:
- лежать внутри `runtime/handlers/*`
- иметь `CANON_THIN_HANDLER = True`
- иметь реальный `handle_*` entrypoint
- не быть marker-only shell

## Architectural meaning

Если этот audit соблюдён:
- boot остаётся wiring-only
- runtime остаётся thin на public entrypoint уровне
- новые входы в систему труднее спрятать
