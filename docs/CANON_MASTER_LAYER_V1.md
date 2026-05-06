# CANON MASTER LAYER V1

CANON_META_PACK: TRUE
CANON_MASTER_LAYER: TRUE

Цель:
явно зафиксировать, что у инженерной конституции есть верхний master layer.

## Что такое master layer

Master layer — это верхний уровень над всеми canonical packs.
Он не заменяет отдельные packs, а проверяет, что они:
- существуют
- не пропали
- перечислены в meta-pack
- видимы в репозитории
- согласованы между собой

## Master layer files

- `docs/CANON_MASTER_CHECKLIST_V1.md`
- `docs/CANON_MASTER_LAYER_V1.md`
- `tests/arch/_canon_master_audit_guard.py`
- `tests/arch/test_master_audit_stack_is_consistent.py`
