# platform_layer.behavior_graph

Role:
- platform storage adapter surface for behavior graph persistence
- canonical public import paths live here
- split `*_part*.py` files are internal fragments only

Rules:
- runtime and core code must import `sqlite_behavior_graph_store.py` or `postgres_behavior_graph_store.py`
- direct imports of split parts are forbidden outside this namespace
