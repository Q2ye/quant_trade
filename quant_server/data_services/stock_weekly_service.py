# stock_weekly_service.py (completed)
from quant_server.data_services.base_service import BaseService
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

    def batch_create(self, data_list: list) -> list:
        """批量创建周线记录"""
        if not data_list:
            return []

        results = []
        with self.session_scope() as session:
            for data in data_list:
                try:
                    # 检查是否已存在相同记录
                    existing = session.query(StockWeekly).filter_by(
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
                        weekly = StockWeekly(**data)
                        session.add(weekly)
                        results.append(weekly)
                except Exception as e:
                    # 记录错误但继续处理其他数据
                    print(f"创建周线记录失败: {e}, 数据: {data}")
                    continue

            session.flush()
        return results