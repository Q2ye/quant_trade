# backtest_position_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..services.base_service import BaseService
from quant_server.db.models.business_models import BacktestPosition


class BacktestPositionService(BaseService):
    """回测持仓服务"""

    def create(self, data: Dict[str, Any]) -> BacktestPosition:
        """创建新回测持仓记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(BacktestPosition).filter_by(
                task_id=data['task_id'],
                trade_date=data['trade_date'],
                ts_code=data['ts_code']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            position = BacktestPosition(**data)
            session.add(position)
            session.flush()
            return position

    def get(self, position_id: int) -> Optional[BacktestPosition]:
        """根据ID获取回测持仓记录"""
        with self.session_scope() as session:
            return session.query(BacktestPosition).filter_by(id=position_id).first()

    def get_task_positions(self, task_id: str, trade_date: datetime = None) -> List[BacktestPosition]:
        """获取任务的持仓记录"""
        with self.session_scope() as session:
            query = session.query(BacktestPosition).filter_by(task_id=task_id)

            if trade_date:
                query = query.filter_by(trade_date=trade_date)

            return query.order_by(BacktestPosition.trade_date, BacktestPosition.ts_code).all()

    def get_task_position_by_symbol(self, task_id: str, ts_code: str,
                                    trade_date: datetime = None) -> Optional[BacktestPosition]:
        """获取任务特定标的的持仓记录"""
        with self.session_scope() as session:
            query = session.query(BacktestPosition).filter_by(
                task_id=task_id,
                ts_code=ts_code
            )

            if trade_date:
                query = query.filter_by(trade_date=trade_date)

            return query.order_by(BacktestPosition.trade_date.desc()).first()

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[BacktestPosition]:
        """批量创建回测持仓记录"""
        results = []
        with self.session_scope() as session:
            for data in data_list:
                # 检查是否已存在
                existing = session.query(BacktestPosition).filter_by(
                    task_id=data['task_id'],
                    trade_date=data['trade_date'],
                    ts_code=data['ts_code']
                ).first()

                if existing:
                    # 更新现有记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    results.append(existing)
                else:
                    # 创建新记录
                    position = BacktestPosition(**data)
                    session.add(position)
                    results.append(position)

            session.flush()
            return results

    def get_position_stats(self, task_id: str, trade_date: datetime = None) -> Dict[str, Any]:
        """获取持仓统计信息"""
        with self.session_scope() as session:
            query = session.query(BacktestPosition).filter_by(task_id=task_id)

            if trade_date:
                query = query.filter_by(trade_date=trade_date)

            positions = query.all()

            total_market_value = sum(float(pos.market_value) for pos in positions)
            position_count = len(positions)

            # 按行业分类（需要关联stock_basic表）
            # 这里简化处理，实际实现需要关联行业信息

            return {
                'position_count': position_count,
                'total_market_value': total_market_value,
                'avg_position_value': total_market_value / position_count if position_count > 0 else 0
            }