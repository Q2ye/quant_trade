from quant_server.db.base_service import BaseService
from quant_server.db.models.models import TradeCalendar


class TradeCalendarService(BaseService):
    """交易日历数据服务"""

    def create(self, data: dict) -> TradeCalendar:
        with self.session_scope() as session:
            instance = TradeCalendar(**data)
            session.add(instance)
            return instance

    def get(self, keys: tuple) -> TradeCalendar:
        exchange, cal_date = keys
        with self.session_scope() as session:
            return session.query(TradeCalendar).get((exchange, cal_date))

    def update(self, keys: tuple, update_data: dict) -> TradeCalendar:
        exchange, cal_date = keys
        with self.session_scope() as session:
            instance = session.query(TradeCalendar).get((exchange, cal_date))
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, keys: tuple) -> None:
        exchange, cal_date = keys
        with self.session_scope() as session:
            instance = session.query(TradeCalendar).get((exchange, cal_date))
            session.delete(instance)

    def filter(self, **filters) -> list[TradeCalendar]:
        with self.session_scope() as session:
            return session.query(TradeCalendar).filter_by(**filters).all()

    def get_all(self) -> list[TradeCalendar]:
        with self.session_scope() as session:
            return session.query(TradeCalendar).all()
