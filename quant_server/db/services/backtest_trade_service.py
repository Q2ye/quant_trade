# backtest_trade_service.py
from typing import List, Optional, Dict, Any

from sqlalchemy import func

from ..services.base_service import BaseService
from quant_server.db.models.business_models import BacktestTrade


class BacktestTradeService(BaseService):
    """回测交易记录服务"""

    def create(self, data: Dict[str, Any]) -> BacktestTrade:
        """创建新回测交易记录"""
        with self.session_scope() as session:
            trade = BacktestTrade(**data)
            session.add(trade)
            session.flush()
            return trade

    def get(self, trade_id: int) -> Optional[BacktestTrade]:
        """根据ID获取回测交易记录"""
        with self.session_scope() as session:
            return session.query(BacktestTrade).filter_by(id=trade_id).first()

    def get_task_trades(self, task_id: str) -> List[BacktestTrade]:
        """获取任务的所有交易记录"""
        with self.session_scope() as session:
            return session.query(BacktestTrade).filter_by(
                task_id=task_id
            ).order_by(BacktestTrade.trade_time).all()

    def get_task_trades_by_symbol(self, task_id: str, ts_code: str) -> List[BacktestTrade]:
        """获取任务特定标的的交易记录"""
        with self.session_scope() as session:
            return session.query(BacktestTrade).filter_by(
                task_id=task_id,
                ts_code=ts_code
            ).order_by(BacktestTrade.trade_time).all()

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[BacktestTrade]:
        """批量创建回测交易记录"""
        results = []
        with self.session_scope() as session:
            for data in data_list:
                trade = BacktestTrade(**data)
                session.add(trade)
                results.append(trade)

            session.flush()
            return results

    def get_trade_stats(self, task_id: str) -> Dict[str, Any]:
        """获取交易统计信息"""
        with self.session_scope() as session:
            # 总交易次数
            total_trades = session.query(BacktestTrade).filter_by(task_id=task_id).count()

            # 买入交易次数
            buy_trades = session.query(BacktestTrade).filter_by(
                task_id=task_id, direction='buy'
            ).count()

            # 卖出交易次数
            sell_trades = session.query(BacktestTrade).filter_by(
                task_id=task_id, direction='sell'
            ).count()

            # 总交易金额
            total_value = session.query(
                func.sum(BacktestTrade.value)
            ).filter_by(task_id=task_id).scalar() or 0

            # 总手续费
            total_commission = session.query(
                func.sum(BacktestTrade.commission)
            ).filter_by(task_id=task_id).scalar() or 0

            # 总税费
            total_tax = session.query(
                func.sum(BacktestTrade.tax)
            ).filter_by(task_id=task_id).scalar() or 0

            return {
                'total_trades': total_trades,
                'buy_trades': buy_trades,
                'sell_trades': sell_trades,
                'total_value': float(total_value),
                'total_commission': float(total_commission),
                'total_tax': float(total_tax),
                'total_cost': float(total_commission + total_tax)
            }