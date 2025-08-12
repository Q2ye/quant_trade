from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockAdjFactor


class StockAdjFactorService(BaseService):
    """股票复权因子数据服务"""

    def create(self, data: dict) -> StockAdjFactor:
        with self.session_scope() as session:
            instance = StockAdjFactor(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> StockAdjFactor:
        with self.session_scope() as session:
            return session.query(StockAdjFactor).get(id)

    def update(self, id: int, update_data: dict) -> StockAdjFactor:
        with self.session_scope() as session:
            instance = session.query(StockAdjFactor).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockAdjFactor).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[StockAdjFactor]:
        with self.session_scope() as session:
            return session.query(StockAdjFactor).filter_by(**filters).all()

    def get_all(self) -> list[StockAdjFactor]:
        with self.session_scope() as session:
            return session.query(StockAdjFactor).all()
