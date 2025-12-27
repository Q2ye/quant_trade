# stock_adjFactor_service.py (completed)
from ..services.base_service import BaseService
from quant_server.shared.database.models.data_models import StockAdjFactor


class StockAdjFactorService(BaseService):
    """股票复权因子数据服务"""

    def create(self, data: dict) -> StockAdjFactor:
        with self.session_scope() as session:
            instance = StockAdjFactor(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, id: int) -> StockAdjFactor:
        with self.session_scope() as session:
            return session.query(StockAdjFactor).get(id)

    def update(self, id: int, update_data: dict) -> StockAdjFactor:
        with self.session_scope() as session:
            instance = session.query(StockAdjFactor).get(id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockAdjFactor).get(id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[StockAdjFactor]:
        with self.session_scope() as session:
            return session.query(StockAdjFactor).filter_by(**filters).all()

    def get_all(self) -> list[StockAdjFactor]:
        with self.session_scope() as session:
            return session.query(StockAdjFactor).all()

    def get_by_stock_date(self, ts_code: str, trade_date):
        """获取指定股票和日期的复权因子"""
        with self.session_scope() as session:
            return session.query(StockAdjFactor).filter(
                StockAdjFactor.ts_code == ts_code,
                StockAdjFactor.trade_date == trade_date
            ).first()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[StockAdjFactor]:
        """获取指定日期范围的复权因子数据"""
        with self.session_scope() as session:
            return session.query(StockAdjFactor).filter(
                StockAdjFactor.ts_code == ts_code,
                StockAdjFactor.trade_date >= start_date,
                StockAdjFactor.trade_date <= end_date
            ).order_by(StockAdjFactor.trade_date).all()

    def get_latest(self, ts_code: str) -> StockAdjFactor:
        """获取指定股票的最新复权因子"""
        with self.session_scope() as session:
            return session.query(StockAdjFactor).filter(
                StockAdjFactor.ts_code == ts_code
            ).order_by(StockAdjFactor.trade_date.desc()).first()

    def batch_create(self, data_list: list[dict]) -> list[StockAdjFactor]:
        """批量创建复权因子记录"""
        with self.session_scope() as session:
            instances = []
            for data in data_list:
                # 检查是否已存在相同股票和日期的记录
                existing = session.query(StockAdjFactor).filter(
                    StockAdjFactor.ts_code == data['ts_code'],
                    StockAdjFactor.trade_date == data['trade_date']
                ).first()

                if existing:
                    # 如果存在，更新记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    instances.append(existing)
                else:
                    # 如果不存在，创建新记录
                    instance = StockAdjFactor(**data)
                    session.add(instance)
                    instances.append(instance)
            session.flush()
            return instances