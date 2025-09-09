# signal_service.py (completed)
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy import desc, func
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.business_models import Signal


class SignalService(BaseService):
    """交易信号服务"""


    def create(self, data: Dict[str, Any]) -> Signal:
        """创建新信号记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(Signal).filter_by(id=data['id']).first()
            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            signal = Signal(**data)
            session.add(signal)
            session.flush()
            return signal

    def get(self, signal_id: int) -> Optional[Signal]:
        """根据信号ID获取信号信息"""
        with self.session_scope() as session:
            return session.query(Signal).filter_by(id=signal_id).first()

    def get_strategy_signals(self, strategy_id: str) -> List[Signal]:
        """获取策略的所有信号"""
        with self.session_scope() as session:
            return session.query(Signal).filter_by(strategy_id=strategy_id).all()

    def get_stock_signals(self, ts_code: str) -> List[Signal]:
        """获取股票的所有信号"""
        with self.session_scope() as session:
            return session.query(Signal).filter_by(ts_code=ts_code).all()

    def get_recent_signals(self, days: int = 7) -> List[Signal]:
        """获取最近N天的信号记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(Signal).filter(
                Signal.signal_time >= cutoff_date
            ).order_by(desc(Signal.signal_time)).all()

    def get_signals_by_type(self, signal_type: str) -> List[Signal]:
        """根据类型获取信号列表"""
        with self.session_scope() as session:
            return session.query(Signal).filter_by(signal_type=signal_type).all()

    def update(self, signal_id: int, update_data: Dict[str, Any]) -> Optional[Signal]:
        """更新信号信息"""
        with self.session_scope() as session:
            signal = session.query(Signal).filter_by(id=signal_id).first()
            if signal:
                for key, value in update_data.items():
                    setattr(signal, key, value)
                return signal
            return None

    def delete(self, signal_id: int) -> bool:
        """删除信号记录"""
        with self.session_scope() as session:
            signal = session.query(Signal).filter_by(id=signal_id).first()
            if signal:
                session.delete(signal)
                return True
            return False

    def delete_old_signals(self, days: int = 30) -> int:
        """删除指定天数前的信号记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            result = session.query(Signal).filter(
                Signal.signal_time < cutoff_date
            ).delete()
            return result

    def count_by_type(self) -> Dict[str, int]:
        """统计各类型的信号数量"""
        with self.session_scope() as session:
            result = session.query(
                Signal.signal_type,
                func.count(Signal.id)
            ).group_by(Signal.signal_type).all()
            return {signal_type: count for signal_type, count in result}

    def count_by_strategy(self) -> Dict[str, int]:
        """统计各策略的信号数量"""
        with self.session_scope() as session:
            result = session.query(
                Signal.strategy_id,
                func.count(Signal.id)
            ).group_by(Signal.strategy_id).all()
            return {strategy_id: count for strategy_id, count in result}

    def get_signal_stats(self, strategy_id: str = None) -> Dict[str, Any]:
        """获取信号统计信息"""
        with self.session_scope() as session:
            query = session.query(Signal)

            if strategy_id:
                query = query.filter_by(strategy_id=strategy_id)

            # 总信号数
            total_count = query.count()

            if total_count == 0:
                return {}

            # 各类型信号数
            type_counts = {
                signal_type: count
                for signal_type, count in query.with_entities(
                    Signal.signal_type, func.count(Signal.id)
                ).group_by(Signal.signal_type).all()
            }

            # 平均信号强度
            avg_strength = query.with_entities(
                func.avg(Signal.strength)
            ).scalar() or 0

            return {
                'total_count': total_count,
                'type_counts': type_counts,
                'avg_strength': avg_strength,
                'buy_ratio': type_counts.get('buy', 0) / total_count * 100 if total_count > 0 else 0,
                'sell_ratio': type_counts.get('sell', 0) / total_count * 100 if total_count > 0 else 0
            }

    def filter(self, **filters) -> list[Signal]:
        """根据条件过滤信号记录"""
        with self.session_scope() as session:
            return session.query(Signal).filter_by(**filters).all()

    def get_signals_by_strategy(self, strategy: str, start_time=None, end_time=None) -> list[Signal]:
        """获取指定策略的信号"""
        with self.session_scope() as session:
            query = session.query(Signal).filter(
                Signal.strategy == strategy
            )

            if start_time:
                query = query.filter(Signal.signal_time >= start_time)
            if end_time:
                query = query.filter(Signal.signal_time <= end_time)

            return query.order_by(Signal.signal_time.desc()).all()

    def get_signals_by_symbol(self, ts_code: str, start_time=None, end_time=None) -> list[Signal]:
        """获取指定股票的信号"""
        with self.session_scope() as session:
            query = session.query(Signal).filter(
                Signal.ts_code == ts_code
            )

            if start_time:
                query = query.filter(Signal.signal_time >= start_time)
            if end_time:
                query = query.filter(Signal.signal_time <= end_time)

            return query.order_by(Signal.signal_time.desc()).all()

    def get_active_signals(self, ts_code: str) -> Optional[Signal]:
        """获取股票当前有效信号"""
        with self.session_scope() as session:
            return session.query(Signal).filter(
                Signal.ts_code == ts_code,
                Signal.signal_type.in_(['buy', 'hold'])
            ).order_by(Signal.signal_time.desc()).first()

    def get_all(self) -> list[Signal]:
        """获取所有信号"""
        with self.session_scope() as session:
            return session.query(Signal).all()