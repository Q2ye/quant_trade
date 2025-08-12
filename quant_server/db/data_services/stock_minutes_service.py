from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockMinutes


class StockMinutesService(BaseService):
    """股票分钟行情数据服务"""

    def create(self, data: dict) -> StockMinutes:
        with self.session_scope() as session:
            instance = StockMinutes(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> StockMinutes:
        with self.session_scope() as session:
            return session.query(StockMinutes).get(id)

    def update(self, id: int, update_data: dict) -> StockMinutes:
        with self.session_scope() as session:
            instance = session.query(StockMinutes).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockMinutes).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[StockMinutes]:
        with self.session_scope() as session:
            return session.query(StockMinutes).filter_by(**filters).all()

    def get_all(self) -> list[StockMinutes]:
        with self.session_scope() as session:
            return session.query(StockMinutes).all()

