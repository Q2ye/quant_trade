# strategy_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import and_, func, desc
from ..services.base_service import BaseService
from quant_server.db.models.business_models import Strategy, StrategyRun, StrategyDailyPerformance


class StrategyService(BaseService):
    """策略信息服务"""

    def create(self, data: Dict[str, Any]) -> Strategy:
        """创建新策略记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(Strategy).filter_by(id=data['id']).first()
            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            strategy = Strategy(**data)
            session.add(strategy)
            session.flush()
            return strategy

    def get(self, strategy_id: str) -> Optional[Strategy]:
        """根据策略ID获取策略信息"""
        with self.session_scope() as session:
            return session.query(Strategy).filter_by(id=strategy_id).first()

    def get_by_name(self, name: str) -> Optional[Strategy]:
        """根据策略名称获取策略信息"""
        with self.session_scope() as session:
            return session.query(Strategy).filter_by(name=name).first()

    def update(self, strategy_id: str, update_data: Dict[str, Any]) -> Optional[Strategy]:
        """更新策略信息"""
        with self.session_scope() as session:
            strategy = session.query(Strategy).filter_by(id=strategy_id).first()
            if strategy:
                for key, value in update_data.items():
                    setattr(strategy, key, value)
                return strategy
            return None

    def delete(self, strategy_id: str) -> bool:
        """删除策略记录"""
        with self.session_scope() as session:
            strategy = session.query(Strategy).filter_by(id=strategy_id).first()
            if strategy:
                session.delete(strategy)
                return True
            return False

    def filter(self, **filters) -> List[Strategy]:
        """根据条件过滤策略记录"""
        with self.session_scope() as session:
            query = session.query(Strategy)
            for key, value in filters.items():
                query = query.filter(getattr(Strategy, key) == value)
            return query.all()

    def get_all(self) -> List[Strategy]:
        """获取所有策略记录"""
        with self.session_scope() as session:
            return session.query(Strategy).all()

    def get_user_strategies(self, user_id: int) -> List[Strategy]:
        """获取用户的所有策略"""
        with self.session_scope() as session:
            return session.query(Strategy).filter_by(user_id=user_id).all()

    def get_active_strategies(self) -> List[Strategy]:
        """获取活跃策略列表"""
        with self.session_scope() as session:
            return session.query(Strategy).filter_by(status='running').all()

    def update_status(self, strategy_id: str, status: str) -> Optional[Strategy]:
        """更新策略状态"""
        with self.session_scope() as session:
            strategy = session.query(Strategy).filter_by(id=strategy_id).first()
            if strategy:
                strategy.status = status
                return strategy
            return None

    def count_by_status(self) -> Dict[str, int]:
        """统计各状态的策略数量"""
        with self.session_scope() as session:
            result = session.query(
                Strategy.status,
                func.count(Strategy.id)
            ).group_by(Strategy.status).all()
            return {status: count for status, count in result}

    def count_by_user(self) -> Dict[int, int]:
        """统计各用户的策略数量"""
        with self.session_scope() as session:
            result = session.query(
                Strategy.user_id,
                func.count(Strategy.id)
            ).group_by(Strategy.user_id).all()
            return {user_id: count for user_id, count in result}


class StrategyRunService(BaseService):
    """策略运行信息服务"""

    def create(self, data: Dict[str, Any]) -> StrategyRun:
        """创建新策略运行记录"""
        with self.session_scope() as session:
            run = StrategyRun(**data)
            session.add(run)
            session.flush()
            return run

    def get(self, run_id: int) -> Optional[StrategyRun]:
        """根据运行ID获取运行信息"""
        with self.session_scope() as session:
            return session.query(StrategyRun).filter_by(id=run_id).first()

    def get_strategy_runs(self, strategy_id: str) -> List[StrategyRun]:
        """获取策略的所有运行记录"""
        with self.session_scope() as session:
            return session.query(StrategyRun).filter_by(strategy_id=strategy_id).all()

    def get_recent_runs(self, days: int = 7) -> List[StrategyRun]:
        """获取最近N天的运行记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(StrategyRun).filter(
                StrategyRun.started_at >= cutoff_date
            ).order_by(desc(StrategyRun.started_at)).all()

    def update(self, run_id: int, update_data: Dict[str, Any]) -> Optional[StrategyRun]:
        """更新运行信息"""
        with self.session_scope() as session:
            run = session.query(StrategyRun).filter_by(id=run_id).first()
            if run:
                for key, value in update_data.items():
                    setattr(run, key, value)
                return run
            return None

    def complete_run(self, run_id: int, status: str = 'completed') -> Optional[StrategyRun]:
        """完成运行记录"""
        with self.session_scope() as session:
            run = session.query(StrategyRun).filter_by(id=run_id).first()
            if run:
                run.stopped_at = datetime.now()
                run.status = status
                return run
            return None

    def delete(self, run_id: int) -> bool:
        """删除运行记录"""
        with self.session_scope() as session:
            run = session.query(StrategyRun).filter_by(id=run_id).first()
            if run:
                session.delete(run)
                return True
            return False

    def delete_old_runs(self, days: int = 30) -> int:
        """删除指定天数前的运行记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            result = session.query(StrategyRun).filter(
                StrategyRun.started_at < cutoff_date
            ).delete()
            return result


class StrategyDailyPerformanceService(BaseService):
    """策略每日绩效信息服务"""

    def create(self, data: Dict[str, Any]) -> StrategyDailyPerformance:
        """创建新策略绩效记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(StrategyDailyPerformance).filter_by(
                strategy_id=data['strategy_id'],
                trade_date=data['trade_date']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            performance = StrategyDailyPerformance(**data)
            session.add(performance)
            session.flush()
            return performance

    def get(self, performance_id: int) -> Optional[StrategyDailyPerformance]:
        """根据绩效ID获取绩效信息"""
        with self.session_scope() as session:
            return session.query(StrategyDailyPerformance).filter_by(id=performance_id).first()

    def get_strategy_performance(self, strategy_id: str) -> List[StrategyDailyPerformance]:
        """获取策略的所有绩效记录"""
        with self.session_scope() as session:
            return session.query(StrategyDailyPerformance).filter_by(
                strategy_id=strategy_id
            ).order_by(StrategyDailyPerformance.trade_date).all()

    def get_recent_performance(self, strategy_id: str, days: int = 30) -> List[StrategyDailyPerformance]:
        """获取策略最近N天的绩效记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(StrategyDailyPerformance).filter(
                and_(
                    StrategyDailyPerformance.strategy_id == strategy_id,
                    StrategyDailyPerformance.trade_date >= cutoff_date
                )
            ).order_by(StrategyDailyPerformance.trade_date).all()

    def update(self, performance_id: int, update_data: Dict[str, Any]) -> Optional[StrategyDailyPerformance]:
        """更新绩效信息"""
        with self.session_scope() as session:
            performance = session.query(StrategyDailyPerformance).filter_by(id=performance_id).first()
            if performance:
                for key, value in update_data.items():
                    setattr(performance, key, value)
                return performance
            return None

    def delete(self, performance_id: int) -> bool:
        """删除绩效记录"""
        with self.session_scope() as session:
            performance = session.query(StrategyDailyPerformance).filter_by(id=performance_id).first()
            if performance:
                session.delete(performance)
                return True
            return False

    def get_best_performing_strategies(self, limit: int = 10) -> List[StrategyDailyPerformance]:
        """获取表现最好的策略（按累计收益率排序）"""
        with self.session_scope() as session:
            # 获取每个策略的最新绩效记录
            subquery = session.query(
                StrategyDailyPerformance.strategy_id,
                func.max(StrategyDailyPerformance.trade_date).label('max_date')
            ).group_by(StrategyDailyPerformance.strategy_id).subquery()

            return session.query(StrategyDailyPerformance).join(
                subquery,
                and_(
                    StrategyDailyPerformance.strategy_id == subquery.c.strategy_id,
                    StrategyDailyPerformance.trade_date == subquery.c.max_date
                )
            ).order_by(desc(StrategyDailyPerformance.total_return)).limit(limit).all()