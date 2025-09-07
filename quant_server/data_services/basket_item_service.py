# basket_item_service.py
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.models import BasketItem


class BasketItemService(BaseService):
    """篮子成分服务"""

    def create(self, data: dict) -> BasketItem:
        with self.session_scope() as session:
            instance = BasketItem(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, basket_item_id: int) -> BasketItem:
        with self.session_scope() as session:
            return session.query(BasketItem).get(basket_item_id)

    def update(self, basket_item_id: int, update_data: dict) -> BasketItem:
        with self.session_scope() as session:
            instance = session.query(BasketItem).get(basket_item_id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, basket_item_id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(BasketItem).get(basket_item_id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[BasketItem]:
        with self.session_scope() as session:
            return session.query(BasketItem).filter_by(**filters).all()

    def get_all(self) -> list[BasketItem]:
        with self.session_scope() as session:
            return session.query(BasketItem).all()

    def get_by_basket(self, basket_id: str) -> list[BasketItem]:
        """获取指定篮子的所有成分"""
        with self.session_scope() as session:
            return session.query(BasketItem).filter_by(basket_id=basket_id).all()

    def get_by_stock(self, ts_code: str) -> list[BasketItem]:
        """获取包含指定股票的所有篮子成分"""
        with self.session_scope() as session:
            return session.query(BasketItem).filter_by(ts_code=ts_code).all()