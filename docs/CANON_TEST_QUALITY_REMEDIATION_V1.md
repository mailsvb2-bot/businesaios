# CANON_TEST_QUALITY_REMEDIATION_V1

Цель:
чинить деградацию arch-tests без ослабления архитектурной конституции.

## Типовые исправления

Если arch-test стал коротким, пустым или import-only:
- добавить AST/import/path-level проверку
- добавить реальный assert payload
- заменить символический smoke на helper-driven architecture check
