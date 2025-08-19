# base_service.py
import logging
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Any, List

logger = logging.getLogger('base_service')

class BaseService:
    """数据库服务基类，提供会话管理和基础CRUD操作的抽象接口"""

    def __init__(self, session: Session = None):
        self.session = session
        if not session:
            logger.warning("服务初始化时未提供数据库会话，某些操作可能受限")

    @contextmanager
    def session_scope(self):
        if not self.session:
            raise RuntimeError("数据库会话未初始化")

        try:
            yield self.session
            self.session.commit()
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"数据库操作失败: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            self.session.rollback()
            logger.error(f"操作失败: {str(e)}", exc_info=True)
            raise

    def create(self, data: dict) -> Any:
        """创建新记录 - 抽象方法"""
        raise NotImplementedError("子类必须实现此方法")

    def get(self, pk: Any) -> Any:
        """根据主键获取记录 - 抽象方法"""
        raise NotImplementedError("子类必须实现此方法")

    def update(self, pk: Any, update_data: dict) -> Any:
        """更新记录 - 抽象方法"""
        raise NotImplementedError("子类必须实现此方法")

    def delete(self, pk: Any) -> None:
        """删除记录 - 抽象方法"""
        raise NotImplementedError("子类必须实现此方法")

    def filter(self, **filters) -> Any:
        """根据条件过滤记录 - 抽象方法"""
        raise NotImplementedError("子类必须实现此方法")

    def get_all(self) -> List[Any]:
        """获取所有记录 - 抽象方法"""
        raise NotImplementedError("子类必须实现此方法")