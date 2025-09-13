# stock_monthly_service.py (completed)
from ..services.base_service import BaseService
from quant_server.db.models.data_models import StockMonthly


class StockMonthlyService(BaseService):
    """股票月线行情数据服务"""

    def create(self, data: dict) -> StockMonthly:
        with self.session_scope() as session:
            instance = StockMonthly(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, stock_monthly_id: int) -> StockMonthly:
        with self.session_scope() as session:
            return session.query(StockMonthly).get(stock_monthly_id)

    def update(self, stock_monthly_id: int, update_data: dict) -> StockMonthly:
        with self.session_scope() as session:
            instance = session.query(StockMonthly).get(stock_monthly_id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, stock_monthly_id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockMonthly).get(stock_monthly_id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[StockMonthly]:
        with self.session_scope() as session:
            return session.query(StockMonthly).filter_by(**filters).all()

    def get_all(self) -> list[StockMonthly]:
        with self.session_scope() as session:
            return session.query(StockMonthly).all()

    def get_by_stock_date(self, ts_code: str, trade_date):
        """获取指定股票和日期的月线数据"""
        with self.session_scope() as session:
            return session.query(StockMonthly).filter(
                StockMonthly.ts_code == ts_code,
                StockMonthly.trade_date == trade_date
            ).first()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[StockMonthly]:
        """获取指定日期范围的月线数据"""
        with self.session_scope() as session:
            return session.query(StockMonthly).filter(
                StockMonthly.ts_code == ts_code,
                StockMonthly.trade_date >= start_date,
                StockMonthly.trade_date <= end_date
            ).order_by(StockMonthly.trade_date).all()

    def get_latest(self, ts_code: str) -> StockMonthly:
        """获取指定股票的最新月线数据"""
        with self.session_scope() as session:
            return session.query(StockMonthly).filter(
                StockMonthly.ts_code == ts_code
            ).order_by(StockMonthly.trade_date.desc()).first()

    def batch_create(self, data_list: list) -> list:
        """批量创建月线记录"""
        if not data_list:
            return []

        results = []
        with self.session_scope() as session:
            for data in data_list:
                try:
                    # 检查是否已存在相同记录
                    existing = session.query(StockMonthly).filter_by(
                        ts_code=data.get('ts_code'),
                        trade_date=data.get('trade_date')
                    ).first()

                    if existing:
                        # 更新现有记录
                        for key, value in data.items():
                            setattr(existing, key, value)
                        results.append(existing)
                    else:
                        # 创建新记录
                        monthly = StockMonthly(**data)
                        session.add(monthly)
                        results.append(monthly)
                except Exception as e:
                    # 记录错误但继续处理其他数据
                    print(f"创建月线记录失败: {e}, 数据: {data}")
                    continue

            session.flush()
        return results