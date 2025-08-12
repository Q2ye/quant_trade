from quantCore.database.base_service import BaseService
from quantCore.models.models import FundAdjFactor


class FundAdjFactorService(BaseService):
    """基金复权因子数据服务"""

    def create(self, data: dict) -> FundAdjFactor:
        with self.session_scope() as session:
            instance = FundAdjFactor(**data)
            session.add(instance)
            return instance

    def get(self, keys: tuple) -> FundAdjFactor:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            return session.query(FundAdjFactor).get((ts_code, trade_date))

    def update(self, keys: tuple, update_data: dict) -> FundAdjFactor:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            instance = session.query(FundAdjFactor).get((ts_code, trade_date))
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, keys: tuple) -> None:
        ts_code, trade_date = keys
        with self.session_scope() as session:
            instance = session.query(FundAdjFactor).get((ts_code, trade_date))
            session.delete(instance)

    def filter(self, **filters) -> list[FundAdjFactor]:
        with self.session_scope() as session:
            return session.query(FundAdjFactor).filter_by(**filters).all()

    def get_all(self) -> list[FundAdjFactor]:
        with self.session_scope() as session:
            return session.query(FundAdjFactor).all()
