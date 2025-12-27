# trading_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import func, desc
from ..services.base_service import BaseService
from quant_server.shared.database.models.business_models import Order, Trade, Position


class OrderService(BaseService):
    """订单信息服务"""

    def create(self, data: Dict[str, Any]) -> Order:
        """创建新订单记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(Order).filter_by(order_id=data['order_id']).first()
            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            order = Order(**data)
            session.add(order)
            session.flush()
            return order

    def get(self, order_id: str) -> Optional[Order]:
        """根据订单ID获取订单信息"""
        with self.session_scope() as session:
            return session.query(Order).filter_by(order_id=order_id).first()

    def get_user_orders(self, user_id: int) -> List[Order]:
        """获取用户的所有订单"""
        with self.session_scope() as session:
            return session.query(Order).filter_by(user_id=user_id).all()

    def get_strategy_orders(self, strategy_id: str) -> List[Order]:
        """获取策略的所有订单"""
        with self.session_scope() as session:
            return session.query(Order).filter_by(strategy_id=strategy_id).all()

    def get_active_orders(self) -> List[Order]:
        """获取活跃订单列表（已提交但未完成）"""
        with self.session_scope() as session:
            return session.query(Order).filter(
                Order.status.in_(['submitted', 'partial_filled'])
            ).all()

    def update(self, order_id: str, update_data: Dict[str, Any]) -> Optional[Order]:
        """更新订单信息"""
        with self.session_scope() as session:
            order = session.query(Order).filter_by(order_id=order_id).first()
            if order:
                for key, value in update_data.items():
                    setattr(order, key, value)
                return order
            return None

    def update_status(self, order_id: str, status: str) -> Optional[Order]:
        """更新订单状态"""
        with self.session_scope() as session:
            order = session.query(Order).filter_by(order_id=order_id).first()
            if order:
                order.status = status
                if status in ['cancelled', 'rejected', 'filled']:
                    order.updated_at = datetime.now()
                return order
            return None

    def cancel_order(self, order_id: str) -> Optional[Order]:
        """取消订单"""
        return self.update_status(order_id, 'cancelled')

    def delete(self, order_id: str) -> bool:
        """删除订单记录"""
        with self.session_scope() as session:
            order = session.query(Order).filter_by(order_id=order_id).first()
            if order:
                session.delete(order)
                return True
            return False

    def get_recent_orders(self, days: int = 7) -> List[Order]:
        """获取最近N天的订单记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(Order).filter(
                Order.submitted_at >= cutoff_date
            ).order_by(desc(Order.submitted_at)).all()

    def count_by_status(self) -> Dict[str, int]:
        """统计各状态的订单数量"""
        with self.session_scope() as session:
            result = session.query(
                Order.status,
                func.count(Order.order_id)
            ).group_by(Order.status).all()
            return {status: count for status, count in result}

    def count_by_direction(self) -> Dict[str, int]:
        """统计买卖方向的订单数量"""
        with self.session_scope() as session:
            result = session.query(
                Order.direction,
                func.count(Order.order_id)
            ).group_by(Order.direction).all()
            return {direction: count for direction, count in result}


class TradeService(BaseService):
    """成交信息服务"""

    def create(self, data: Dict[str, Any]) -> Trade:
        """创建新成交记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(Trade).filter_by(trade_id=data['trade_id']).first()
            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            trade = Trade(**data)
            session.add(trade)
            session.flush()
            return trade

    def get(self, trade_id: str) -> Optional[Trade]:
        """根据成交ID获取成交信息"""
        with self.session_scope() as session:
            return session.query(Trade).filter_by(trade_id=trade_id).first()

    def get_order_trades(self, order_id: str) -> List[Trade]:
        """获取订单的所有成交记录"""
        with self.session_scope() as session:
            return session.query(Trade).filter_by(order_id=order_id).all()

    def get_user_trades(self, user_id: int) -> List[Trade]:
        """获取用户的所有成交记录"""
        with self.session_scope() as session:
            return session.query(Trade).join(Order).filter(Order.user_id == user_id).all()

    def get_recent_trades(self, days: int = 7) -> List[Trade]:
        """获取最近N天的成交记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(Trade).filter(
                Trade.trade_time >= cutoff_date
            ).order_by(desc(Trade.trade_time)).all()

    def update(self, trade_id: str, update_data: Dict[str, Any]) -> Optional[Trade]:
        """更新成交信息"""
        with self.session_scope() as session:
            trade = session.query(Trade).filter_by(trade_id=trade_id).first()
            if trade:
                for key, value in update_data.items():
                    setattr(trade, key, value)
                return trade
            return None

    def delete(self, trade_id: str) -> bool:
        """删除成交记录"""
        with self.session_scope() as session:
            trade = session.query(Trade).filter_by(trade_id=trade_id).first()
            if trade:
                session.delete(trade)
                return True
            return False

    def get_daily_trade_summary(self, date: datetime = None) -> Dict[str, Any]:
        """获取每日交易汇总信息"""
        if date is None:
            date = datetime.now().date()

        with self.session_scope() as session:
            # 计算总成交额和总成交量
            total_result = session.query(
                func.sum(Trade.volume * Trade.price).label('total_amount'),
                func.sum(Trade.volume).label('total_volume'),
                func.count(Trade.trade_id).label('trade_count')
            ).filter(
                func.date(Trade.trade_time) == date
            ).first()

            # 计算买卖方向统计
            direction_result = session.query(
                Order.direction,
                func.sum(Trade.volume * Trade.price).label('amount'),
                func.sum(Trade.volume).label('volume'),
                func.count(Trade.trade_id).label('count')
            ).join(Order).filter(
                func.date(Trade.trade_time) == date
            ).group_by(Order.direction).all()

            return {
                'date': date,
                'total_amount': total_result.total_amount or 0,
                'total_volume': total_result.total_volume or 0,
                'trade_count': total_result.trade_count or 0,
                'by_direction': {direction: {
                    'amount': amount,
                    'volume': volume,
                    'count': count
                } for direction, amount, volume, count in direction_result}
            }


class PositionService(BaseService):
    """持仓信息服务"""

    def create_or_update(self, data: Dict[str, Any]) -> Position:
        """创建或更新持仓记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(Position).filter_by(
                user_id=data['user_id'],
                ts_code=data['ts_code']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                existing.last_update = datetime.now()
                return existing

            # 创建新记录
            position = Position(**data)
            session.add(position)
            session.flush()
            return position

    def get(self, position_id: int) -> Optional[Position]:
        """根据持仓ID获取持仓信息"""
        with self.session_scope() as session:
            return session.query(Position).filter_by(id=position_id).first()

    def get_user_position(self, user_id: int, ts_code: str) -> Optional[Position]:
        """获取用户的特定股票持仓"""
        with self.session_scope() as session:
            return session.query(Position).filter_by(
                user_id=user_id,
                ts_code=ts_code
            ).first()

    def get_user_positions(self, user_id: int) -> List[Position]:
        """获取用户的所有持仓"""
        with self.session_scope() as session:
            return session.query(Position).filter_by(user_id=user_id).all()

    def update(self, position_id: int, update_data: Dict[str, Any]) -> Optional[Position]:
        """更新持仓信息"""
        with self.session_scope() as session:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                for key, value in update_data.items():
                    setattr(position, key, value)
                position.last_update = datetime.now()
                return position
            return None

    def delete(self, position_id: int) -> bool:
        """删除持仓记录"""
        with self.session_scope() as session:
            position = session.query(Position).filter_by(id=position_id).first()
            if position:
                session.delete(position)
                return True
            return False

    def clear_user_positions(self, user_id: int) -> bool:
        """清空用户的所有持仓"""
        with self.session_scope() as session:
            positions = session.query(Position).filter_by(user_id=user_id).all()
            for position in positions:
                session.delete(position)
            return True

    def get_total_value(self, user_id: int) -> float:
        """获取用户持仓总市值"""
        with self.session_scope() as session:
            result = session.query(
                func.sum(Position.market_value)
            ).filter_by(user_id=user_id).scalar()
            return result or 0

    def get_position_distribution(self, user_id: int) -> Dict[str, float]:
        """获取用户持仓分布"""
        with self.session_scope() as session:
            total_value = self.get_total_value(user_id)
            if total_value == 0:
                return {}

            positions = session.query(Position).filter_by(user_id=user_id).all()
            return {
                position.ts_code: position.market_value / total_value * 100
                for position in positions
            }