import logging

from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from quant_server.db.models.data_models import StockSTList
from quant_server.db.services.base_service import BaseService

logger = logging.getLogger(__name__)


class StockSTListService(BaseService):
    """ST股票列表服务类"""

    def __init__(self, session: Session):
        super().__init__(session)

    def create(self, data: dict) -> StockSTList:
        """创建ST股票记录"""
        with self.session_scope() as session:
            st_stock = StockSTList(**data)
            session.add(st_stock)
            return st_stock

    def get(self, id: int) -> Optional[StockSTList]:
        """根据ID获取ST股票记录"""
        with self.session_scope() as session:
            return session.query(StockSTList).filter(StockSTList.id == id).first()

    def get_by_code_and_date(self, ts_code: str, trade_date: datetime) -> Optional[StockSTList]:
        """根据股票代码和日期获取ST股票记录"""
        with self.session_scope() as session:
            return session.query(StockSTList).filter(
                StockSTList.ts_code == ts_code,
                StockSTList.trade_date == trade_date
            ).first()

    def update(self, id: int, update_data: dict) -> Optional[StockSTList]:
        """更新ST股票记录"""
        with self.session_scope() as session:
            st_stock = session.query(StockSTList).filter(StockSTList.id == id).first()

            if st_stock:
                for key, value in update_data.items():
                    setattr(st_stock, key, value)

            return st_stock

    def delete(self, id: int) -> bool:
        """删除ST股票记录"""
        with self.session_scope() as session:
            st_stock = session.query(StockSTList).filter(StockSTList.id == id).first()

            if st_stock:
                session.delete(st_stock)
                return True
            return False

    def filter(self, **filters) -> List[StockSTList]:
        """根据条件过滤ST股票记录"""
        with self.session_scope() as session:
            query = session.query(StockSTList)
            for attr, value in filters.items():
                if hasattr(StockSTList, attr):
                    query = query.filter(getattr(StockSTList, attr) == value)
            return query.all()

    def get_all(self) -> List[StockSTList]:
        """获取所有ST股票记录"""
        with self.session_scope() as session:
            return session.query(StockSTList).all()

    def get_stocks_by_date(self, trade_date: datetime) -> List[StockSTList]:
        """获取指定日期的所有ST股票"""
        with self.session_scope() as session:
            return session.query(StockSTList).filter(
                StockSTList.trade_date == trade_date
            ).all()

    def get_stock_history(self, ts_code: str) -> List[StockSTList]:
        """获取指定股票的所有ST记录历史"""
        with self.session_scope() as session:
            return session.query(StockSTList).filter(
                StockSTList.ts_code == ts_code
            ).order_by(StockSTList.trade_date).all()

    def is_st_stock(self, ts_code: str, trade_date: datetime) -> bool:
        """检查指定股票在指定日期是否为ST股票"""
        with self.session_scope() as session:
            st_record = session.query(StockSTList).filter(
                StockSTList.ts_code == ts_code,
                StockSTList.trade_date == trade_date
            ).first()
            return st_record is not None