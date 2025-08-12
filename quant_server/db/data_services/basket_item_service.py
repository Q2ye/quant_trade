from quant_server.db.base_service import BaseService
from quant_server.db.models.models import BasketItem


class BasketItemService(BaseService):
    """篮子成分服务"""

    def create(self, data: dict) -> BasketItem:
        with self.session_scope() as session:
            instance = BasketItem(**data)
            session.add(instance)
            return instance

    def get(self, id: int) -> BasketItem:
        with self.session_scope() as session:
            return session.query(BasketItem).get(id)

    def update(self, id: int, update_data: dict) -> BasketItem:
        with self.session_scope() as session:
            instance = session.query(BasketItem).get(id)
            for key, value in update_data.items():
                setattr(instance, key, value)
            return instance

    def delete(self, id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(BasketItem).get(id)
            session.delete(instance)

    def filter(self, **filters) -> list[BasketItem]:
        with self.session_scope() as session:
            return session.query(BasketItem).filter_by(**filters).all()

    def get_all(self) -> list[BasketItem]:
        with self.session_scope() as session:
            return session.query(BasketItem).all()