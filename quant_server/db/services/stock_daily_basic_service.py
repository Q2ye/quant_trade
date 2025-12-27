# stock_daily_basic_service.py (completed)
from ..services.base_service import BaseService
from quant_server.shared.database.models.data_models import StockDailyBasic


class StockDailyBasicService(BaseService):
    """股票每日基本面数据服务"""

    def create(self, data: dict) -> StockDailyBasic:
        with self.session_scope() as session:
            instance = StockDailyBasic(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, stock_daily_basic_id: int) -> StockDailyBasic:
        with self.session_scope() as session:
            return session.query(StockDailyBasic).get(stock_daily_basic_id)

    def update(self, stock_daily_basic_id: int, update_data: dict) -> StockDailyBasic:
        with self.session_scope() as session:
            instance = session.query(StockDailyBasic).get(stock_daily_basic_id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, stock_daily_basic_id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockDailyBasic).get(stock_daily_basic_id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[StockDailyBasic]:
        with self.session_scope() as session:
            return session.query(StockDailyBasic).filter_by(**filters).all()

    def get_all(self) -> list[StockDailyBasic]:
        with self.session_scope() as session:
            return session.query(StockDailyBasic).all()

    def get_by_stock_date(self, ts_code: str, trade_date):
        """获取指定股票和日期的基本面数据"""
        with self.session_scope() as session:
            return session.query(StockDailyBasic).filter(
                StockDailyBasic.ts_code == ts_code,
                StockDailyBasic.trade_date == trade_date
            ).first()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[StockDailyBasic]:
        """获取指定日期范围的基本面数据"""
        with self.session_scope() as session:
            return session.query(StockDailyBasic).filter(
                StockDailyBasic.ts_code == ts_code,
                StockDailyBasic.trade_date >= start_date,
                StockDailyBasic.trade_date <= end_date
            ).order_by(StockDailyBasic.trade_date).all()

    def get_latest(self, ts_code: str) -> StockDailyBasic:
        """获取指定股票的最新基本面数据"""
        with self.session_scope() as session:
            return session.query(StockDailyBasic).filter(
                StockDailyBasic.ts_code == ts_code
            ).order_by(StockDailyBasic.trade_date.desc()).first()

    def batch_create(self, data_list: list[dict]) -> list[StockDailyBasic]:
        """批量创建每日基本面数据记录"""
        with self.session_scope() as session:
            instances = []
            for data in data_list:
                # 检查是否已存在相同股票和日期的记录
                existing = session.query(StockDailyBasic).filter(
                    StockDailyBasic.ts_code == data['ts_code'],
                    StockDailyBasic.trade_date == data['trade_date']
                ).first()

                if existing:
                    # 如果存在，更新记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    instances.append(existing)
                else:
                    # 如果不存在，创建新记录
                    instance = StockDailyBasic(**data)
                    session.add(instance)
                    instances.append(instance)
            session.flush()
            return instances