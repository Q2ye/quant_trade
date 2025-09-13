# performance_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import func, desc, and_
from ..services.base_service import BaseService
from quant_server.db.models.business_models import AccountDailyPerformance


class AccountDailyPerformanceService(BaseService):
    """账户每日绩效信息服务"""

    def create(self, data: Dict[str, Any]) -> AccountDailyPerformance:
        """创建新账户绩效记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(AccountDailyPerformance).filter_by(
                user_id=data['user_id'],
                trade_date=data['trade_date']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            performance = AccountDailyPerformance(**data)
            session.add(performance)
            session.flush()
            return performance

    def get(self, performance_id: int) -> Optional[AccountDailyPerformance]:
        """根据绩效ID获取绩效信息"""
        with self.session_scope() as session:
            return session.query(AccountDailyPerformance).filter_by(id=performance_id).first()

    def get_user_performance(self, user_id: int) -> List[AccountDailyPerformance]:
        """获取用户的所有绩效记录"""
        with self.session_scope() as session:
            return session.query(AccountDailyPerformance).filter_by(
                user_id=user_id
            ).order_by(AccountDailyPerformance.trade_date).all()

    def get_recent_performance(self, user_id: int, days: int = 30) -> List[AccountDailyPerformance]:
        """获取用户最近N天的绩效记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(AccountDailyPerformance).filter(
                and_(
                    AccountDailyPerformance.user_id == user_id,
                    AccountDailyPerformance.trade_date >= cutoff_date
                )
            ).order_by(AccountDailyPerformance.trade_date).all()

    def update(self, performance_id: int, update_data: Dict[str, Any]) -> Optional[AccountDailyPerformance]:
        """更新绩效信息"""
        with self.session_scope() as session:
            performance = session.query(AccountDailyPerformance).filter_by(id=performance_id).first()
            if performance:
                for key, value in update_data.items():
                    setattr(performance, key, value)
                return performance
            return None

    def delete(self, performance_id: int) -> bool:
        """删除绩效记录"""
        with self.session_scope() as session:
            performance = session.query(AccountDailyPerformance).filter_by(id=performance_id).first()
            if performance:
                session.delete(performance)
                return True
            return False

    def get_user_summary(self, user_id: int) -> Dict[str, Any]:
        """获取用户绩效摘要"""
        with self.session_scope() as session:
            # 获取最新绩效记录
            latest = session.query(AccountDailyPerformance).filter_by(
                user_id=user_id
            ).order_by(desc(AccountDailyPerformance.trade_date)).first()

            if not latest:
                return {}

            # 计算累计收益率
            first = session.query(AccountDailyPerformance).filter_by(
                user_id=user_id
            ).order_by(AccountDailyPerformance.trade_date).first()

            if first and first.total_asset > 0:
                total_return = (latest.total_asset - first.total_asset) / first.total_asset * 100
            else:
                total_return = 0

            # 计算最大回撤
            max_drawdown = session.query(
                func.min(AccountDailyPerformance.daily_return)
            ).filter_by(user_id=user_id).scalar() or 0

            return {
                'latest_date': latest.trade_date,
                'total_asset': latest.total_asset,
                'cash': latest.cash,
                'market_value': latest.market_value,
                'total_return': total_return,
                'max_drawdown': max_drawdown
            }

    def get_top_performers(self, limit: int = 10) -> List[AccountDailyPerformance]:
        """获取表现最好的用户（按总资产排序）"""
        with self.session_scope() as session:
            # 获取每个用户的最新绩效记录
            subquery = session.query(
                AccountDailyPerformance.user_id,
                func.max(AccountDailyPerformance.trade_date).label('max_date')
            ).group_by(AccountDailyPerformance.user_id).subquery()

            return session.query(AccountDailyPerformance).join(
                subquery,
                and_(
                    AccountDailyPerformance.user_id == subquery.c.user_id,
                    AccountDailyPerformance.trade_date == subquery.c.max_date
                )
            ).order_by(desc(AccountDailyPerformance.total_asset)).limit(limit).all()