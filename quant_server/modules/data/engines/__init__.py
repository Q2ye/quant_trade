# 2026-08 D 批清理：clean/quality/research 三引擎仅被死链 DataManager 实例化，已随 managers 包删除。
# 数据同步引擎 DataSyncEngine 由 data/__init__.py 与 handlers.py 直接从 sync_engine 模块导入，不受影响。
__all__ = []
