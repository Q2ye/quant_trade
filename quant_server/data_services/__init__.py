import logging
from typing import Optional

from quant_server.data_services.data_sync_service import DataSyncService
from quant_server.db.data_service import DataService
from quant_server.db.session import db_session_scope



logger = logging.getLogger(__name__)

# 全局服务实例
_data_sync_service: Optional[DataSyncService] = None
_data_service: Optional[DataService] = None


def init_services():
    """初始化所有服务"""
    global _data_sync_service, _data_service

    try:
        # 使用数据库会话作用域来初始化服务
        with db_session_scope() as db_session:
            _data_sync_service = DataSyncService(db_session)
            _data_service = DataService(db_session)
        logger.info("服务初始化成功")
        return True
    except Exception as e:
        logger.error(f"服务初始化失败: {str(e)}")
        return False


def get_data_sync_service() -> DataSyncService:
    """获取数据同步服务"""
    if _data_sync_service is None:
        raise RuntimeError("数据同步服务未初始化")
    return _data_sync_service


def get_data_service() -> DataService:
    """获取数据服务"""
    if _data_service is None:
        raise RuntimeError("数据服务未初始化")
    return _data_service