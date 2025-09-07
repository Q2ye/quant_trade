# stock_adjustedPrices_service.py (completed)
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.models import StockAdjustedPrices


class StockAdjustedPricesService(BaseService):
    """股票复权价格数据服务"""

    def create(self, data: dict) -> StockAdjustedPrices:
        with self.session_scope() as session:
            instance = StockAdjustedPrices(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, id: int) -> StockAdjustedPrices:
        with self.session_scope() as session:
            return session.query(StockAdjustedPrices).get(id)

    def update(self, id: int, update_data: dict) -> StockAdjustedPrices:
        with self.session_scope() as session:
            instance = session.query(StockAdjustedPrices).get(id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockAdjustedPrices).get(id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[StockAdjustedPrices]:
        with self.session_scope() as session:
            return session.query(StockAdjustedPrices).filter_by(**filters).all()

    def get_all(self) -> list[StockAdjustedPrices]:
        with self.session_scope() as session:
            return session.query(StockAdjustedPrices).all()

    def get_by_stock_date(self, ts_code: str, trade_date, adj_type: str = None):
        """获取指定股票和日期的复权价格"""
        with self.session_scope() as session:
            query = session.query(StockAdjustedPrices).filter(
                StockAdjustedPrices.ts_code == ts_code,
                StockAdjustedPrices.trade_date == trade_date
            )
            if adj_type:
                query = query.filter(StockAdjustedPrices.adj_type == adj_type)
            return query.first()

    def get_by_date_range(self, ts_code: str, start_date, end_date, adj_type: str = None) -> list[StockAdjustedPrices]:
        """获取指定日期范围的复权价格数据"""
        with self.session_scope() as session:
            query = session.query(StockAdjustedPrices).filter(
                StockAdjustedPrices.ts_code == ts_code,
                StockAdjustedPrices.trade_date >= start_date,
                StockAdjustedPrices.trade_date <= end_date
            )
            if adj_type:
                query = query.filter(StockAdjustedPrices.adj_type == adj_type)
            return query.order_by(StockAdjustedPrices.trade_date).all()

    def get_latest(self, ts_code: str, adj_type: str = None) -> StockAdjustedPrices:
        """获取指定股票的最新复权价格"""
        with self.session_scope() as session:
            query = session.query(StockAdjustedPrices).filter(
                StockAdjustedPrices.ts_code == ts_code
            )
            if adj_type:
                query = query.filter(StockAdjustedPrices.adj_type == adj_type)
            return query.order_by(StockAdjustedPrices.trade_date.desc()).first()