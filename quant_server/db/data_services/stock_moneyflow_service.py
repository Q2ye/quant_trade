# stock_moneyflow_service.py
from typing import Optional, Type

from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockMoneyflow


class StockMoneyflowService(BaseService):
    """资金流向服务"""

    def create(self, data: dict) -> StockMoneyflow:
        """创建新资金流向记录"""
        with self.session_scope() as session:
            flow = StockMoneyflow(**data)
            session.add(flow)
            session.flush()
            return flow

    def get(self, id: int) -> Optional[StockMoneyflow]:
        """根据ID获取资金流向记录"""
        return self.filter(id=id).first()

    def update(self, id: int, update_data: dict) -> Optional[StockMoneyflow]:
        """更新资金流向记录"""
        with self.session_scope() as session:
            flow = session.query(StockMoneyflow).get(id)
            if flow:
                for key, value in update_data.items():
                    setattr(flow, key, value)
            return flow

    def delete(self, id: int) -> None:
        """删除资金流向记录"""
        with self.session_scope() as session:
            flow = session.query(StockMoneyflow).get(id)
            if flow:
                session.delete(flow)

    def filter(self, **filters) -> list[Type[StockMoneyflow]]:
        """根据条件过滤资金流向记录"""
        return self.session.query(StockMoneyflow).filter_by(**filters).all()

    def get_by_code_and_date(self, ts_code: str, trade_date) -> Optional[StockMoneyflow]:
        """根据股票代码和日期获取资金流向"""
        return self.filter(ts_code=ts_code, trade_date=trade_date).first()

    def get_large_net_inflow(self, date, threshold=1000000) -> list[Type[StockMoneyflow]]:
        """获取当日大单净流入超过阈值的股票"""
        return self.session.query(StockMoneyflow).filter(
            StockMoneyflow.trade_date == date,
            StockMoneyflow.net_mf_amount > threshold
        ).all()

    def get_consecutive_inflow(self, ts_code: str, days=3) -> list[Type[StockMoneyflow]]:
        """检测连续资金净流入"""
        return self.session.query(StockMoneyflow).filter(
            StockMoneyflow.ts_code == ts_code,
            StockMoneyflow.net_mf_amount > 0
        ).order_by(StockMoneyflow.trade_date.desc()).limit(days).all()