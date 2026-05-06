# CANON POST HARD LOCK CHECKLIST V1

После hard lock проект должен постепенно проходить следующие cleanup-шаги:

1. Явно документировать legacy / compat namespaces
2. Не допускать пустых compat-обёрток без marker-а
3. Не допускать новой логики в compat/shim-модулях
4. Сохранять один final decision authority
5. Сохранять один irreversible execution path
6. Постепенно переводить hotspot legacy paths на advisory surfaces
