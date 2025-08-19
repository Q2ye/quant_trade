# stock_weekly_service.py (completed)
from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockWeekly


class StockWeeklyService(BaseService):
    """股票周线行情数据服务"""

    def create(self, data: dict) -> StockWeekly:
        with self.session_scope() as session:
            instance = StockWeekly(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, id: int) -> StockWeekly:
        with self.session_scope() as session:
            return session.query(StockWeekly).get(id)

    def update(self, id: int, update_data: dict) -> StockWeekly:
        with self.session_scope() as session:
            instance = session.query(StockWeekly).get(id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockWeekly).get(id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[StockWeekly]:
        with self.session_scope() as session:
            return session.query(StockWeekly).filter_by(**filters).all()

    def get_all(self) -> list[StockWeekly]:
        with self.session_scope() as session:
            return session.query(StockWeekly).all()

    def get_by_stock_date(self, ts_code: str, trade_date):
        """获取指定股票和日期的周线数据"""
        with self.session_scope() as session:
            return session.query(StockWeekly).filter(
                StockWeekly.ts_code == ts_code,
                StockWeekly.trade_date == trade_date
            ).first()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[StockWeekly]:
        """获取指定日期范围的周线数据"""
        with self.session_scope() as session:
            return session.query(StockWeekly).filter(
                StockWeekly.ts_code == ts_code,
                StockWeekly.trade_date >= start_date,
                StockWeekly.trade_date <= end_date
            ).order_by(StockWeekly.trade_date).all()

    def get_latest(self, ts_code: str) -> StockWeekly:
        """获取指定股票的最新周线数据"""
        with self.session_scope() as session:
            return session.query(StockWeekly).filter(
                StockWeekly.ts_code == ts_code
            ).order_by(StockWeekly.trade_date.desc()).first()

    def get_by_week_range(self, ts_code: str, start_week, end_week) -> list[StockWeekly]:
        """获取指定周范围的周线数据"""
        with self.session_scope() as session:
            return session.query(StockWeekly).filter(
                StockWeekly.ts_code == ts_code,
                StockWeekly.week_start >= start_week,
                StockWeekly.week_end <= end_week
            ).order_by(StockWeekly.week_start).all()