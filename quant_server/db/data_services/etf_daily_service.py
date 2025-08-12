from quant_server.db.base_service import BaseService
from quant_server.db.models.models import EtfDaily


class EtfDailyService(BaseService):
    """ETF日线行情数据服务"""

    def create(self, data: dict) -> EtfDaily:
        with self.session_scope() as session:
            instance = EtfDaily(**data)
            session.add(instance)
            return instance

    def get(self, keys: tuple) -> EtfDaily:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            return session.query(EtfDaily).get((ts_code, trade_date))

    def update(self, keys: tuple, update_data: dict) -> EtfDaily:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            instance = session.query(EtfDaily).get((ts_code, trade_date))
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, keys: tuple) -> None:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            instance = session.query(EtfDaily).get((ts_code, trade_date))
            session.delete(instance)

    def filter(self, **filters) -> list[EtfDaily]:
        with self.session_scope() as session:
            return session.query(EtfDaily).filter_by(**filters).all()

    def get_all(self) -> list[EtfDaily]:
        with self.session_scope() as session:
            return session.query(EtfDaily).all()
