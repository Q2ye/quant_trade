# backtest_equity_curve_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime

from quant_server.data_services.base_service import BaseService
from quant_server.db.models.business_models import BacktestEquityCurve


class BacktestEquityCurveService(BaseService):
    """回测净值曲线服务"""

    def create(self, data: Dict[str, Any]) -> BacktestEquityCurve:
        """创建新净值曲线记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(BacktestEquityCurve).filter_by(
                task_id=data['task_id'],
                trade_date=data['trade_date']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            curve = BacktestEquityCurve(**data)
            session.add(curve)
            session.flush()
            return curve

    def get(self, curve_id: int) -> Optional[BacktestEquityCurve]:
        """根据ID获取净值曲线记录"""
        with self.session_scope() as session:
            return session.query(BacktestEquityCurve).filter_by(id=curve_id).first()

    def update(self, curve_id: int, update_data: Dict[str, Any]) -> Optional[BacktestEquityCurve]:
        """更新净值曲线记录"""
        with self.session_scope() as session:
            curve = session.query(BacktestEquityCurve).filter_by(id=curve_id).first()
            if curve:
                for key, value in update_data.items():
                    setattr(curve, key, value)
                return curve
            return None

    def delete(self, curve_id: int) -> bool:
        """删除净值曲线记录"""
        with self.session_scope() as session:
            curve = session.query(BacktestEquityCurve).filter_by(id=curve_id).first()
            if curve:
                session.delete(curve)
                return True
            return False

    def get_task_equity_curve(self, task_id: str) -> List[BacktestEquityCurve]:
        """获取任务的完整净值曲线"""
        with self.session_scope() as session:
            return session.query(BacktestEquityCurve).filter_by(
                task_id=task_id
            ).order_by(BacktestEquityCurve.trade_date).all()

    def get_task_equity_by_date(self, task_id: str, trade_date: datetime) -> Optional[BacktestEquityCurve]:
        """获取任务特定日期的净值记录"""
        with self.session_scope() as session:
            return session.query(BacktestEquityCurve).filter_by(
                task_id=task_id,
                trade_date=trade_date
            ).first()

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[BacktestEquityCurve]:
        """批量创建净值曲线记录"""
        results = []
        with self.session_scope() as session:
            for data in data_list:
                # 检查是否已存在
                existing = session.query(BacktestEquityCurve).filter_by(
                    task_id=data['task_id'],
                    trade_date=data['trade_date']
                ).first()

                if existing:
                    # 更新现有记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    results.append(existing)
                else:
                    # 创建新记录
                    curve = BacktestEquityCurve(**data)
                    session.add(curve)
                    results.append(curve)

            session.flush()
            return results