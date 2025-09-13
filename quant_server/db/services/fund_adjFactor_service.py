# fund_adjFactor_service.py (completed)
from ..services.base_service import BaseService
from quant_server.db.models.data_models import FundAdjFactor


class FundAdjFactorService(BaseService):
    """基金复权因子数据服务"""

    def create(self, data: dict) -> FundAdjFactor:
        with self.session_scope() as session:
            instance = FundAdjFactor(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, keys: tuple) -> FundAdjFactor:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            return session.query(FundAdjFactor).get((ts_code, trade_date))

    def update(self, keys: tuple, update_data: dict) -> FundAdjFactor:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            instance = session.query(FundAdjFactor).get((ts_code, trade_date))
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, keys: tuple) -> None:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            instance = session.query(FundAdjFactor).get((ts_code, trade_date))
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[FundAdjFactor]:
        with self.session_scope() as session:
            return session.query(FundAdjFactor).filter_by(**filters).all()

    def get_all(self) -> list[FundAdjFactor]:
        with self.session_scope() as session:
            return session.query(FundAdjFactor).all()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[FundAdjFactor]:
        """获取指定日期范围的复权因子数据"""
        with self.session_scope() as session:
            return session.query(FundAdjFactor).filter(
                FundAdjFactor.ts_code == ts_code,
                FundAdjFactor.trade_date >= start_date,
                FundAdjFactor.trade_date <= end_date
            ).order_by(FundAdjFactor.trade_date).all()

    def get_latest(self, ts_code: str) -> FundAdjFactor:
        """获取指定基金的最新复权因子"""
        with self.session_scope() as session:
            return session.query(FundAdjFactor).filter(
                FundAdjFactor.ts_code == ts_code
            ).order_by(FundAdjFactor.trade_date.desc()).first()