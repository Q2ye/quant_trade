# stock_daily_service.py
from typing import List, Optional,Type

from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockDaily


class StockDailyService(BaseService):
    """股票日线行情服务"""

    def create(self, data: dict) -> StockDaily:
        """创建新日线记录"""
        with self.session_scope() as session:
            daily = StockDaily(**data)
            session.add(daily)
            session.flush()
            return daily

    def get(self, id: int) -> Optional[StockDaily]:
        """根据ID获取日线记录"""
        return self.filter(id=id).first()

    def update(self, id: int, update_data: dict) -> Optional[StockDaily]:
        """更新日线记录"""
        with self.session_scope() as session:
            daily = session.query(StockDaily).get(id)
            if daily:
                for key, value in update_data.items():
                    setattr(daily, key, value)
            return daily

    def delete(self, id: int) -> None:
        """删除日线记录"""
        with self.session_scope() as session:
            daily = session.query(StockDaily).get(id)
            if daily:
                session.delete(daily)

    def filter(self, **filters) -> list[Type[StockDaily]]:
        """根据条件过滤日线记录"""
        return self.session.query(StockDaily).filter_by(**filters).all()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[Type[StockDaily]]:
        """获取指定日期范围内的行情数据"""
        return self.session.query(StockDaily).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date >= start_date,
            StockDaily.trade_date <= end_date
        ).order_by(StockDaily.trade_date).all()

    def get_latest_by_ts_code(self, ts_code: str) -> Optional[StockDaily]:
        """获取指定股票的最新行情"""
        return self.session.query(StockDaily).filter(
            StockDaily.ts_code == ts_code
        ).order_by(StockDaily.trade_date.desc()).first()

    def get_by_code_and_date(self, ts_code: str, trade_date) -> Optional[StockDaily]:
        """根据股票代码和日期获取日线记录"""
        return self.filter(ts_code=ts_code, trade_date=trade_date).first()

    def get_price_history(self, ts_code: str, start_date, end_date) -> list[Type[StockDaily]]:
        """获取指定时间范围内的价格历史"""
        return self.session.query(StockDaily).filter(
            StockDaily.ts_code == ts_code,
            StockDaily.trade_date.between(start_date, end_date)
        ).order_by(StockDaily.trade_date).all()

    def get_last_trading_day_data(self, ts_code: str) -> Optional[StockDaily]:
        """获取最近交易日的行情数据"""
        return self.filter(ts_code=ts_code).order_by(
            StockDaily.trade_date.desc()
        ).first()