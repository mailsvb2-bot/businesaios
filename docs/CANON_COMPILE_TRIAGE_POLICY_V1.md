# CANON COMPILE TRIAGE POLICY V1

Цель:
не скрывать compile-проблемы за общим `compileall`, а локализовать их до конкретных файлов.

## Главный закон

Если общий compile-проход возвращает не-ноль, инженерный проход должен:
- локализовать реальные offending files
- зафиксировать результат в triage report
- не делать вид, что весь репозиторий полностью чистый без доказательства

## Staged rule

Сначала triage идёт по:
- всем `.py` файлам через file-level compile
- затем добавляются targeted fixes
- только потом расширяется canonical audit scope
