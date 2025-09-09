# stock_minutes_service.py (completed)
from datetime import timedelta

from quant_server.data_services.base_service import BaseService
from quant_server.db.models.data_models import StockMinutes


class StockMinutesService(BaseService):
    """股票分钟行情数据服务"""

    def create(self, data: dict) -> StockMinutes:
        with self.session_scope() as session:
            instance = StockMinutes(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, id: int) -> StockMinutes:
        with self.session_scope() as session:
            return session.query(StockMinutes).get(id)

    def update(self, id: int, update_data: dict) -> StockMinutes:
        with self.session_scope() as session:
            instance = session.query(StockMinutes).get(id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockMinutes).get(id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[StockMinutes]:
        with self.session_scope() as session:
            return session.query(StockMinutes).filter_by(**filters).all()

    def get_all(self) -> list[StockMinutes]:
        with self.session_scope() as session:
            return session.query(StockMinutes).all()

    def get_by_time_range(self, ts_code: str, freq: str, start_time, end_time) -> list[StockMinutes]:
        """获取指定时间范围的分钟数据"""
        with self.session_scope() as session:
            return session.query(StockMinutes).filter(
                StockMinutes.ts_code == ts_code,
                StockMinutes.freq == freq,
                StockMinutes.trade_time >= start_time,
                StockMinutes.trade_time <= end_time
            ).order_by(StockMinutes.trade_time).all()

    def get_latest(self, ts_code: str, freq: str) -> StockMinutes:
        """获取指定股票和频率的最新分钟数据"""
        with self.session_scope() as session:
            return session.query(StockMinutes).filter(
                StockMinutes.ts_code == ts_code,
                StockMinutes.freq == freq
            ).order_by(StockMinutes.trade_time.desc()).first()

    def get_intraday(self, ts_code: str, trade_date, freq: str = '1min') -> list[StockMinutes]:
        """获取指定交易日的日内分钟数据"""
        with self.session_scope() as session:
            return session.query(StockMinutes).filter(
                StockMinutes.ts_code == ts_code,
                StockMinutes.freq == freq,
                StockMinutes.trade_time >= trade_date,
                StockMinutes.trade_time < trade_date + timedelta(days=1)
            ).order_by(StockMinutes.trade_time).all()