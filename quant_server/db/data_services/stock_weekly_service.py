from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockWeekly


class StockWeeklyService(BaseService):
    """股票周线行情数据服务"""

    def create(self, data: dict) -> StockWeekly:
        with self.session_scope() as session:
            instance = StockWeekly(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> StockWeekly:
        with self.session_scope() as session:
            return session.query(StockWeekly).get(id)

    def update(self, id: int, update_data: dict) -> StockWeekly:
        with self.session_scope() as session:
            instance = session.query(StockWeekly).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockWeekly).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[StockWeekly]:
        with self.session_scope() as session:
            return session.query(StockWeekly).filter_by(**filters).all()

    def get_all(self) -> list[StockWeekly]:
        with self.session_scope() as session:
            return session.query(StockWeekly).all()
