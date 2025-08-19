# stock_daily_limit_service.py (completed)
from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockDailyLimit


class StockDailyLimitService(BaseService):
    """股票每日涨跌停数据服务"""

    def create(self, data: dict) -> StockDailyLimit:
        with self.session_scope() as session:
            instance = StockDailyLimit(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, stock_daily_limit_id: int) -> StockDailyLimit:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).get(stock_daily_limit_id)

    def update(self, stock_daily_limit_id: int, update_data: dict) -> StockDailyLimit:
        with self.session_scope() as session:
            instance = session.query(StockDailyLimit).get(stock_daily_limit_id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, stock_daily_limit_id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockDailyLimit).get(stock_daily_limit_id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[StockDailyLimit]:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter_by(**filters).all()

    def get_all(self) -> list[StockDailyLimit]:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).all()

    def get_by_stock_date(self, ts_code: str, trade_date):
        """获取指定股票和日期的涨跌停数据"""
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter(
                StockDailyLimit.ts_code == ts_code,
                StockDailyLimit.trade_date == trade_date
            ).first()

    def get_limit_up_stocks(self, trade_date):
        """获取指定日期涨停的股票"""
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter(
                StockDailyLimit.trade_date == trade_date,
                StockDailyLimit.up_limit == StockDailyLimit.up_limit
            ).all()

    def get_limit_down_stocks(self, trade_date):
        """获取指定日期跌停的股票"""
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter(
                StockDailyLimit.trade_date == trade_date,
                StockDailyLimit.down_limit == StockDailyLimit.down_limit
            ).all()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[StockDailyLimit]:
        """获取指定日期范围的涨跌停数据"""
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter(
                StockDailyLimit.ts_code == ts_code,
                StockDailyLimit.trade_date >= start_date,
                StockDailyLimit.trade_date <= end_date
            ).order_by(StockDailyLimit.trade_date).all()