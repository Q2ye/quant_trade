# etf_minute_service.py (completed)
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.data_models import EtfMinute


class EtfMinuteService(BaseService):
    """ETF分钟行情数据服务"""

    def create(self, data: dict) -> EtfMinute:
        with self.session_scope() as session:
            instance = EtfMinute(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, id: int) -> EtfMinute:
        with self.session_scope() as session:
            return session.query(EtfMinute).get(id)

    def update(self, id: int, update_data: dict) -> EtfMinute:
        with self.session_scope() as session:
            instance = session.query(EtfMinute).get(id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(EtfMinute).get(id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[EtfMinute]:
        with self.session_scope() as session:
            return session.query(EtfMinute).filter_by(**filters).all()

    def get_all(self) -> list[EtfMinute]:
        with self.session_scope() as session:
            return session.query(EtfMinute).all()

    def get_by_time_range(self, ts_code: str, freq: str, start_time, end_time) -> list[EtfMinute]:
        """获取指定时间范围的分钟数据"""
        with self.session_scope() as session:
            return session.query(EtfMinute).filter(
                EtfMinute.ts_code == ts_code,
                EtfMinute.freq == freq,
                EtfMinute.trade_time >= start_time,
                EtfMinute.trade_time <= end_time
            ).order_by(EtfMinute.trade_time).all()

    def get_latest(self, ts_code: str, freq: str) -> EtfMinute:
        """获取指定ETF和频率的最新分钟数据"""
        with self.session_scope() as session:
            return session.query(EtfMinute).filter(
                EtfMinute.ts_code == ts_code,
                EtfMinute.freq == freq
            ).order_by(EtfMinute.trade_time.desc()).first()