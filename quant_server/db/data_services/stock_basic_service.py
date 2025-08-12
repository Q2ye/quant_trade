# stock_basic_service.py
from typing import  Type

from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockBasic


class StockBasicService(BaseService):
    """股票基础信息服务"""

    # 实现基类要求的抽象方法
    def create(self, data: dict) -> StockBasic:
        """创建新股票记录"""
        with self.session_scope() as session:
            stock = StockBasic(**data)
            session.add(stock)
            session.flush()
            return stock

    def get(self, ts_code: str) -> StockBasic:
        """根据股票代码获取股票信息"""
        return self.filter(ts_code=ts_code).first()

    def update(self, ts_code: str, update_data: dict) -> StockBasic:
        """更新股票信息"""
        with self.session_scope() as session:
            stock = session.query(StockBasic).get(ts_code)
            for key, value in update_data.items():
                setattr(stock, key, value)
            return stock

    def delete(self, ts_code: str) -> None:
        """删除股票记录"""
        with self.session_scope() as session:
            stock = session.query(StockBasic).get(ts_code)
            session.delete(stock)

    def filter(self, **filters) -> list[Type[StockBasic]]:
        """根据条件过滤股票记录"""
        return self.session.query(StockBasic).filter_by(**filters).all()

    def get_all(self) -> list[Type[StockBasic]]:
        """获取所有股票记录"""
        return self.session.query(StockBasic).all()

    # 原有业务方法 - 修复参数问题
    def get_by_ts_code(self, ts_code: str) -> StockBasic:
        """根据股票代码获取股票信息"""
        return self.filter(ts_code=ts_code).first()

    def get_by_symbol(self, symbol: str) -> StockBasic:
        """根据股票符号获取股票信息"""
        return self.filter(symbol=symbol).first()

    def list_active_stocks(self) -> list[Type[StockBasic]]:
        """获取上市状态的股票列表"""
        return self.filter(list_status='L')