from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockDailyLimit


class StockDailyLimitService(BaseService):
    """股票每日涨跌停数据服务"""

    def create(self, data: dict) -> StockDailyLimit:
        with self.session_scope() as session:
            instance = StockDailyLimit(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> StockDailyLimit:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).get(id)

    def update(self, id: int, update_data: dict) -> StockDailyLimit:
        with self.session_scope() as session:
            instance = session.query(StockDailyLimit).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockDailyLimit).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[StockDailyLimit]:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter_by(**filters).all()

    def get_all(self) -> list[StockDailyLimit]:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).all()
