from quant_server.db.base_service import BaseService
from quant_server.db.models.models import EtfMinute


class EtfMinuteService(BaseService):
    """ETF分钟行情数据服务"""

    def create(self, data: dict) -> EtfMinute:
        with self.session_scope() as session:
            instance = EtfMinute(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> EtfMinute:
        with self.session_scope() as session:
            return session.query(EtfMinute).get(id)

    def update(self, id: int, update_data: dict) -> EtfMinute:
        with self.session_scope() as session:
            instance = session.query(EtfMinute).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(EtfMinute).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[EtfMinute]:
        with self.session_scope() as session:
            return session.query(EtfMinute).filter_by(**filters).all()

    def get_all(self) -> list[EtfMinute]:
        with self.session_scope() as session:
            return session.query(EtfMinute).all()
