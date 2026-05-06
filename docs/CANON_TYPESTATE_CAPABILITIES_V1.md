# CANON TYPESTATE CAPABILITIES V1

Цель:
зафиксировать не только import boundaries, но и capability boundaries:
какие архитектурные способности имеет право иметь каждый слой и каждый тип модуля.

## Capability vocabulary

### Advisory capabilities
Разрешены:
- enrich
- explain
- score
- observe
- validate
- guard
- read
- write
- project
- build

### Restricted capabilities
Запрещены в advisory-зонах:
- select
- choose
- pick
- resolve
- decide
- finalize
- issue
- apply
- execute
- dispatch
- route
