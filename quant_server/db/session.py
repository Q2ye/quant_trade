# session.py
import logging
from typing import Optional
from contextlib import contextmanager

from sqlalchemy.orm import Session

from quant_server.db.db_connector import DbConnector

logger = logging.getLogger(__name__)

# 全局数据库连接器实例
_db_connector: Optional[DbConnector] = None

def init_db() -> bool:
    """初始化数据库连接"""
    global _db_connector

    try:
        _db_connector = DbConnector()
        if _db_connector.connect():
            logger.info("数据库连接初始化成功")
            return True
        else:
            logger.error("数据库连接初始化失败")
            return False
    except Exception as e:
        logger.error(f"数据库初始化异常: {str(e)}")
        return False

def get_db_session() -> Session:
    """获取数据库会话"""
    if _db_connector is None:
        raise RuntimeError("数据库未初始化，请先调用 init_db()")
    return _db_connector.get_session()

@contextmanager
def db_session_scope():
    """数据库会话作用域上下文管理器"""
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"数据库操作失败: {str(e)}")
        raise
    finally:
        session.close()

def close_db():
    """关闭数据库连接"""
    global _db_connector
    if _db_connector:
        _db_connector.close()
        _db_connector = None
        logger.info("数据库连接已关闭")