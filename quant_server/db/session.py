# session.py
import logging
from typing import Optional

from quant_server.db.db_connector import DbConnector

logger = logging.getLogger('session')

# 全局数据库连接器实例
_db_connector: Optional[DbConnector] = None


def init_db(config: dict = None) -> bool:
    """初始化数据库连接"""
    global _db_connector

    try:
        _db_connector = DbConnector(config)
        if _db_connector.connect():
            logger.info("数据库连接初始化成功")
            return True
        else:
            logger.error("数据库连接初始化失败")
            return False
    except Exception as e:
        logger.error(f"数据库初始化异常: {str(e)}")
        return False


def get_db():
    """获取数据库会话"""
    if _db_connector is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    return _db_connector.get_session()


def close_db():
    """关闭数据库连接"""
    global _db_connector
    if _db_connector:
        _db_connector.close()
        _db_connector = None
        logger.info("数据库连接已关闭")