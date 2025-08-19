# etf_daily_service.py (completed)
from quant_server.db.base_service import BaseService
from quant_server.db.models.models import EtfDaily


class EtfDailyService(BaseService):
    """ETF日线行情数据服务"""

    def create(self, data: dict) -> EtfDaily:
        with self.session_scope() as session:
            instance = EtfDaily(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, keys: tuple) -> EtfDaily:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            return session.query(EtfDaily).get((ts_code, trade_date))

    def update(self, keys: tuple, update_data: dict) -> EtfDaily:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            instance = session.query(EtfDaily).get((ts_code, trade_date))
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, keys: tuple) -> None:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            instance = session.query(EtfDaily).get((ts_code, trade_date))
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[EtfDaily]:
        with self.session_scope() as session:
            return session.query(EtfDaily).filter_by(**filters).all()

    def get_all(self) -> list[EtfDaily]:
        with self.session_scope() as session:
            return session.query(EtfDaily).all()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[EtfDaily]:
        """获取指定日期范围的ETF日线数据"""
        with self.session_scope() as session:
            return session.query(EtfDaily).filter(
                EtfDaily.ts_code == ts_code,
                EtfDaily.trade_date >= start_date,
                EtfDaily.trade_date <= end_date
            ).order_by(EtfDaily.trade_date).all()

    def get_latest(self, ts_code: str) -> EtfDaily:
        """获取指定ETF的最新日线数据"""
        with self.session_scope() as session:
            return session.query(EtfDaily).filter(
                EtfDaily.ts_code == ts_code
            ).order_by(EtfDaily.trade_date.desc()).first()