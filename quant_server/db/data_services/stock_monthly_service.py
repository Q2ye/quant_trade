from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockMonthly


class StockMonthlyService(BaseService):
    """股票月线行情数据服务"""

    def create(self, data: dict) -> StockMonthly:
        with self.session_scope() as session:
            instance = StockMonthly(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> StockMonthly:
        with self.session_scope() as session:
            return session.query(StockMonthly).get(id)

    def update(self, id: int, update_data: dict) -> StockMonthly:
        with self.session_scope() as session:
            instance = session.query(StockMonthly).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockMonthly).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[StockMonthly]:
        with self.session_scope() as session:
            return session.query(StockMonthly).filter_by(**filters).all()

    def get_all(self) -> list[StockMonthly]:
        with self.session_scope() as session:
            return session.query(StockMonthly).all()

