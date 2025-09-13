# basket_service.py
from typing import List, Optional, Dict, Any

from sqlalchemy import func

from ..services.base_service import BaseService
from quant_server.db.models.business_models import Basket, BasketItem


class BasketService(BaseService):
    """篮子信息服务"""

    def create(self, data: Dict[str, Any]) -> Basket:
        """创建新篮子记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(Basket).filter_by(id=data['id']).first()
            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            basket = Basket(**data)
            session.add(basket)
            session.flush()
            return basket

    def get(self, basket_id: str) -> Optional[Basket]:
        """根据篮子ID获取篮子信息"""
        with self.session_scope() as session:
            return session.query(Basket).filter_by(id=basket_id).first()

    def get_by_name(self, name: str) -> Optional[Basket]:
        """根据篮子名称获取篮子信息"""
        with self.session_scope() as session:
            return session.query(Basket).filter_by(name=name).first()

    def update(self, basket_id: str, update_data: Dict[str, Any]) -> Optional[Basket]:
        """更新篮子信息"""
        with self.session_scope() as session:
            basket = session.query(Basket).filter_by(id=basket_id).first()
            if basket:
                for key, value in update_data.items():
                    setattr(basket, key, value)
                return basket
            return None

    def delete(self, basket_id: str) -> bool:
        """删除篮子记录"""
        with self.session_scope() as session:
            basket = session.query(Basket).filter_by(id=basket_id).first()
            if basket:
                session.delete(basket)
                return True
            return False

    def filter(self, **filters) -> List[Basket]:
        """根据条件过滤篮子记录"""
        with self.session_scope() as session:
            query = session.query(Basket)
            for key, value in filters.items():
                query = query.filter(getattr(Basket, key) == value)
            return query.all()

    def get_all(self) -> List[Basket]:
        """获取所有篮子记录"""
        with self.session_scope() as session:
            return session.query(Basket).all()

    def search_by_name(self, name: str) -> List[Basket]:
        """根据名称搜索篮子"""
        with self.session_scope() as session:
            return session.query(Basket).filter(
                Basket.name.like(f"%{name}%")
            ).all()

    def count_items(self, basket_id: str) -> int:
        """统计篮子中的项目数量"""
        with self.session_scope() as session:
            return session.query(BasketItem).filter_by(basket_id=basket_id).count()


class BasketItemService(BaseService):
    """篮子项目信息服务"""

    def create(self, data: Dict[str, Any]) -> BasketItem:
        """创建新篮子项目记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(BasketItem).filter_by(
                basket_id=data['basket_id'],
                ts_code=data['ts_code']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            item = BasketItem(**data)
            session.add(item)
            session.flush()
            return item

    def get(self, item_id: int) -> Optional[BasketItem]:
        """根据项目ID获取项目信息"""
        with self.session_scope() as session:
            return session.query(BasketItem).filter_by(id=item_id).first()

    def get_basket_items(self, basket_id: str) -> List[BasketItem]:
        """获取篮子的所有项目"""
        with self.session_scope() as session:
            return session.query(BasketItem).filter_by(basket_id=basket_id).all()

    def update(self, item_id: int, update_data: Dict[str, Any]) -> Optional[BasketItem]:
        """更新项目信息"""
        with self.session_scope() as session:
            item = session.query(BasketItem).filter_by(id=item_id).first()
            if item:
                for key, value in update_data.items():
                    setattr(item, key, value)
                return item
            return None

    def update_weight(self, item_id: int, weight: float) -> Optional[BasketItem]:
        """更新项目权重"""
        with self.session_scope() as session:
            item = session.query(BasketItem).filter_by(id=item_id).first()
            if item:
                item.weight = weight
                return item
            return None

    def delete(self, item_id: int) -> bool:
        """删除项目记录"""
        with self.session_scope() as session:
            item = session.query(BasketItem).filter_by(id=item_id).first()
            if item:
                session.delete(item)
                return True
            return False

    def delete_basket_items(self, basket_id: str) -> bool:
        """删除篮子的所有项目"""
        with self.session_scope() as session:
            items = session.query(BasketItem).filter_by(basket_id=basket_id).all()
            for item in items:
                session.delete(item)
            return True

    def normalize_weights(self, basket_id: str) -> bool:
        """归一化篮子中项目的权重"""
        with self.session_scope() as session:
            items = session.query(BasketItem).filter_by(basket_id=basket_id).all()
            if not items:
                return False

            total_weight = sum(item.weight for item in items)
            if total_weight == 0:
                return False

            for item in items:
                item.weight = item.weight / total_weight

            return True

    def get_total_weight(self, basket_id: str) -> float:
        """获取篮子中项目的总权重"""
        with self.session_scope() as session:
            result = session.query(
                func.sum(BasketItem.weight)
            ).filter_by(basket_id=basket_id).scalar()
            return result or 0