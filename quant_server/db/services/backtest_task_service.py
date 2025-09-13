# backtest_task_service.py
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from sqlalchemy import  desc

from ..services.base_service import BaseService
from quant_server.db.models.business_models import BacktestTask


class BacktestTaskService(BaseService):
    """回测任务服务"""

    def create(self, data: Dict[str, Any]) -> BacktestTask:
        """创建新回测任务"""
        with self.session_scope() as session:
            task = BacktestTask(**data)
            session.add(task)
            session.flush()
            return task

    def get(self, task_id: str) -> Optional[BacktestTask]:
        """根据ID获取回测任务"""
        with self.session_scope() as session:
            return session.query(BacktestTask).filter_by(id=task_id).first()

    def update(self, task_id: str, update_data: Dict[str, Any]) -> Optional[BacktestTask]:
        """更新回测任务信息"""
        with self.session_scope() as session:
            task = session.query(BacktestTask).filter_by(id=task_id).first()
            if task:
                for key, value in update_data.items():
                    setattr(task, key, value)
                return task
            return None

    def delete(self, task_id: str) -> bool:
        """删除回测任务"""
        with self.session_scope() as session:
            task = session.query(BacktestTask).filter_by(id=task_id).first()
            if task:
                session.delete(task)
                return True
            return False

    def filter(self, **filters) -> List[BacktestTask]:
        """根据条件过滤回测任务"""
        with self.session_scope() as session:
            query = session.query(BacktestTask)
            for key, value in filters.items():
                query = query.filter(getattr(BacktestTask, key) == value)
            return query.all()

    def get_all(self) -> List[BacktestTask]:
        """获取所有回测任务"""
        with self.session_scope() as session:
            return session.query(BacktestTask).all()

    def get_user_tasks(self, user_id: int) -> List[BacktestTask]:
        """获取用户的所有回测任务"""
        with self.session_scope() as session:
            return session.query(BacktestTask).filter_by(user_id=user_id).all()

    def get_by_status(self, status: str) -> List[BacktestTask]:
        """根据状态获取回测任务"""
        with self.session_scope() as session:
            return session.query(BacktestTask).filter_by(status=status).all()

    def update_progress(self, task_id: str, progress: float) -> Optional[BacktestTask]:
        """更新回测任务进度"""
        return self.update(task_id, {"progress": progress})

    def complete_task(self, task_id: str, result: Dict[str, Any] = None,
                      error_message: str = None) -> Optional[BacktestTask]:
        """完成回测任务"""
        update_data: Dict[str, Union[str, datetime, int, float, Dict[str, Any]]] = {
            "status": "completed" if not error_message else "failed",
            "completed_at": datetime.now(),
            "progress": 100
        }

        if result:
            update_data["result"] = result
        if error_message:
            update_data["error_message"] = error_message

        return self.update(task_id, update_data)

    def get_recent_tasks(self, days: int = 7) -> List[BacktestTask]:
        """获取最近N天的回测任务"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(BacktestTask).filter(
                BacktestTask.created_at >= cutoff_date
            ).order_by(desc(BacktestTask.created_at)).all()