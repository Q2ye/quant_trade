# stock_signal_service.py (completed)
from typing import Optional
from datetime import datetime, timedelta

from quant_server.db.base_service import BaseService
from quant_server.db.models.models import StockSignal


class StockSignalService(BaseService):
    """交易信号服务"""

    def create(self, data: dict) -> StockSignal:
        """创建新信号记录"""
        with self.session_scope() as session:
            signal = StockSignal(**data)
            session.add(signal)
            session.flush()
            return signal

    def get(self, signal_id: str) -> Optional[StockSignal]:
        """根据ID获取信号"""
        with self.session_scope() as session:
            return session.query(StockSignal).get(signal_id)

    def update(self, signal_id: str, update_data: dict) -> Optional[StockSignal]:
        """更新信号记录"""
        with self.session_scope() as session:
            signal = session.query(StockSignal).get(signal_id)
            if signal:
                for key, value in update_data.items():
                    setattr(signal, key, value)
            return signal

    def delete(self, signal_id: str) -> None:
        """删除信号记录"""
        with self.session_scope() as session:
            signal = session.query(StockSignal).get(signal_id)
            if signal:
                session.delete(signal)

    def filter(self, **filters) -> list[StockSignal]:
        """根据条件过滤信号记录"""
        with self.session_scope() as session:
            return session.query(StockSignal).filter_by(**filters).all()

    def get_signals_by_strategy(self, strategy: str, start_time=None, end_time=None) -> list[StockSignal]:
        """获取指定策略的信号"""
        with self.session_scope() as session:
            query = session.query(StockSignal).filter(
                StockSignal.strategy == strategy
            )

            if start_time:
                query = query.filter(StockSignal.signal_time >= start_time)
            if end_time:
                query = query.filter(StockSignal.signal_time <= end_time)

            return query.order_by(StockSignal.signal_time.desc()).all()

    def get_signals_by_symbol(self, ts_code: str, start_time=None, end_time=None) -> list[StockSignal]:
        """获取指定股票的信号"""
        with self.session_scope() as session:
            query = session.query(StockSignal).filter(
                StockSignal.ts_code == ts_code
            )

            if start_time:
                query = query.filter(StockSignal.signal_time >= start_time)
            if end_time:
                query = query.filter(StockSignal.signal_time <= end_time)

            return query.order_by(StockSignal.signal_time.desc()).all()

    def get_active_signals(self, ts_code: str) -> Optional[StockSignal]:
        """获取股票当前有效信号"""
        with self.session_scope() as session:
            return session.query(StockSignal).filter(
                StockSignal.ts_code == ts_code,
                StockSignal.signal_type.in_(['buy', 'hold'])
            ).order_by(StockSignal.signal_time.desc()).first()

    def get_recent_signals(self, days: int = 7) -> list[StockSignal]:
        """获取最近几天的信号"""
        with self.session_scope() as session:
            cutoff_date = datetime.now() - timedelta(days=days)
            return session.query(StockSignal).filter(
                StockSignal.signal_time >= cutoff_date
            ).order_by(StockSignal.signal_time.desc()).all()

    def get_all(self) -> list[StockSignal]:
        """获取所有信号"""
        with self.session_scope() as session:
            return session.query(StockSignal).all()