from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockDailyBasic


class StockDailyBasicService(BaseService):
    """股票每日基本面数据服务"""

    def create(self, data: dict) -> StockDailyBasic:
        with self.session_scope() as session:
            instance = StockDailyBasic(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> StockDailyBasic:
        with self.session_scope() as session:
            return session.query(StockDailyBasic).get(id)

    def update(self, id: int, update_data: dict) -> StockDailyBasic:
        with self.session_scope() as session:
            instance = session.query(StockDailyBasic).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockDailyBasic).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[StockDailyBasic]:
        with self.session_scope() as session:
            return session.query(StockDailyBasic).filter_by(**filters).all()

    def get_all(self) -> list[StockDailyBasic]:
        with self.session_scope() as session:
            return session.query(StockDailyBasic).all()
