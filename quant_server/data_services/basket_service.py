# basket_service.py (completed)
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.models import Basket, BasketItem


class BasketService(BaseService):
    """交易篮子服务"""

    def create_basket(self, name: str, description: str = None):
        """创建新篮子"""
        with self.session_scope() as session:
            basket = Basket(name=name, description=description)
            session.add(basket)
            session.flush()
            return basket

    def add_to_basket(self, basket_id: str, ts_code: str, weight: float):
        """添加股票到篮子"""
        with self.session_scope() as session:
            item = BasketItem(
                basket_id=basket_id,
                ts_code=ts_code,
                weight=weight
            )
            session.add(item)
            session.flush()
            return item

    def get_basket(self, basket_id: str):
        """获取篮子详情"""
        with self.session_scope() as session:
            return session.query(Basket).get(basket_id)

    def update_basket(self, basket_id: str, update_data: dict):
        """更新篮子信息"""
        with self.session_scope() as session:
            basket = session.query(Basket).get(basket_id)
            if basket:
                for key, value in update_data.items():
                    setattr(basket, key, value)
            return basket

    def delete_basket(self, basket_id: str):
        """删除篮子"""
        with self.session_scope() as session:
            basket = session.query(Basket).get(basket_id)
            if basket:
                # 先删除所有篮子成分
                session.query(BasketItem).filter_by(basket_id=basket_id).delete()
                session.delete(basket)

    def get_basket_items(self, basket_id: str):
        """获取篮子成分股"""
        with self.session_scope() as session:
            return session.query(BasketItem).filter_by(basket_id=basket_id).all()

    def rebalance_basket(self, basket_id: str, new_composition: dict):
        """重新平衡篮子成分"""
        with self.session_scope() as session:
            # 删除现有成分
            session.query(BasketItem).filter_by(basket_id=basket_id).delete()

            # 添加新成分
            for ts_code, weight in new_composition.items():
                item = BasketItem(
                    basket_id=basket_id,
                    ts_code=ts_code,
                    weight=weight
                )
                session.add(item)
            session.flush()

    def get_all_baskets(self):
        """获取所有篮子"""
        with self.session_scope() as session:
            return session.query(Basket).all()

    def filter_baskets(self, **filters):
        """根据条件过滤篮子"""
        with self.session_scope() as session:
            return session.query(Basket).filter_by(**filters).all()