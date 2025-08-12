from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockAdjustedPrices


class StockAdjustedPricesService(BaseService):
    """股票复权价格数据服务"""

    def create(self, data: dict) -> StockAdjustedPrices:
        with self.session_scope() as session:
            instance = StockAdjustedPrices(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> StockAdjustedPrices:
        with self.session_scope() as session:
            return session.query(StockAdjustedPrices).get(id)

    def update(self, id: int, update_data: dict) -> StockAdjustedPrices:
        with self.session_scope() as session:
            instance = session.query(StockAdjustedPrices).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockAdjustedPrices).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[StockAdjustedPrices]:
        with self.session_scope() as session:
            return session.query(StockAdjustedPrices).filter_by(**filters).all()

    def get_all(self) -> list[StockAdjustedPrices]:
        with self.session_scope() as session:
            return session.query(StockAdjustedPrices).all()

