# data_sync_task_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from sqlalchemy import func, desc
from ..services.base_service import BaseService
from quant_server.db.models.business_models import DataSyncTask


class DataSyncTaskService(BaseService):
    """数据同步任务信息服务"""

    def create(self, data: Dict[str, Any]) -> DataSyncTask:
        """创建新数据同步任务记录"""
        with self.session_scope() as session:
            # 提取参数
            parameters = data.get('parameters', {})

            # 创建任务对象
            task_data = {
                "task_type": data.get("task_type", ""),
                "status": data.get("status", "pending"),
                "start_time": data.get("start_time"),
                "parameters": parameters,
                "total_records": 0
            }

            task = DataSyncTask(**task_data)
            session.add(task)
            session.flush()
            session.refresh(task)
            return task

    def get(self, task_id: int) -> Optional[DataSyncTask]:
        """根据任务ID获取任务信息"""
        with self.session_scope() as session:
            return session.query(DataSyncTask).filter_by(id=task_id).first()

    def get_recent_tasks(self, days: int = 7) -> List[DataSyncTask]:
        """获取最近N天的任务记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            return session.query(DataSyncTask).filter(
                DataSyncTask.created_at >= cutoff_date
            ).order_by(desc(DataSyncTask.created_at)).all()

    def get_tasks_by_type(self, task_type: str) -> List[DataSyncTask]:
        """根据类型获取任务列表"""
        with self.session_scope() as session:
            return session.query(DataSyncTask).filter_by(task_type=task_type).all()

    def get_active_tasks(self) -> List[DataSyncTask]:
        """获取活跃任务列表（运行中）"""
        with self.session_scope() as session:
            return session.query(DataSyncTask).filter_by(status='running').all()

    def update(self, task_id: int, update_data: Dict[str, Any]) -> Optional[DataSyncTask]:
        """更新任务信息"""
        with self.session_scope() as session:
            task = session.query(DataSyncTask).filter_by(id=task_id).first()
            if task:
                for key, value in update_data.items():
                    setattr(task, key, value)
                return task
            return None

    def update_status(self, task_id: int, status: str) -> Optional[DataSyncTask]:
        """更新任务状态"""
        with self.session_scope() as session:
            task = session.query(DataSyncTask).filter_by(id=task_id).first()
            if task:
                task.status = status
                if status in ['completed', 'failed']:
                    task.end_time = datetime.now()
                return task
            return None

    def start_task(self, task_id: int) -> Optional[DataSyncTask]:
        """开始任务"""
        with self.session_scope() as session:
            task = session.query(DataSyncTask).filter_by(id=task_id).first()
            if task:
                task.status = 'running'
                task.start_time = datetime.now()
                return task
            return None

    def complete_task(self, task_id: int, total_records: int = 0) -> Optional[DataSyncTask]:
        """完成任务"""
        with self.session_scope() as session:
            task = session.query(DataSyncTask).filter_by(id=task_id).first()
            if task:
                task.status = 'completed'
                task.end_time = datetime.now()
                task.total_records = total_records
                return task
            return None

    def fail_task(self, task_id: int, error_message: str) -> Optional[DataSyncTask]:
        """标记任务失败"""
        with self.session_scope() as session:
            task = session.query(DataSyncTask).filter_by(id=task_id).first()
            if task:
                task.status = 'failed'
                task.end_time = datetime.now()
                task.error_message = error_message
                return task
            return None

    def delete(self, task_id: int) -> bool:
        """删除任务记录"""
        with self.session_scope() as session:
            task = session.query(DataSyncTask).filter_by(id=task_id).first()
            if task:
                session.delete(task)
                return True
            return False

    def delete_old_tasks(self, days: int = 30) -> int:
        """删除指定天数前的任务记录"""
        cutoff_date = datetime.now() - timedelta(days=days)
        with self.session_scope() as session:
            result = session.query(DataSyncTask).filter(
                DataSyncTask.created_at < cutoff_date
            ).delete()
            return result

    def count_by_status(self) -> Dict[str, int]:
        """统计各状态的任务数量"""
        with self.session_scope() as session:
            result = session.query(
                DataSyncTask.status,
                func.count(DataSyncTask.id)
            ).group_by(DataSyncTask.status).all()
            return {status: count for status, count in result}

    def count_by_type(self) -> Dict[str, int]:
        """统计各类型的任务数量"""
        with self.session_scope() as session:
            result = session.query(
                DataSyncTask.task_type,
                func.count(DataSyncTask.id)
            ).group_by(DataSyncTask.task_type).all()
            return {task_type: count for task_type, count in result}

    def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        with self.session_scope() as session:
            # 总任务数
            total_count = session.query(func.count(DataSyncTask.id)).scalar() or 0

            # 成功任务数
            success_count = session.query(func.count(DataSyncTask.id)).filter_by(
                status='completed'
            ).scalar() or 0

            # 失败任务数
            failed_count = session.query(func.count(DataSyncTask.id)).filter_by(
                status='failed'
            ).scalar() or 0

            # 运行中任务数
            running_count = session.query(func.count(DataSyncTask.id)).filter_by(
                status='running'
            ).scalar() or 0

            # 总同步记录数
            total_records = session.query(func.sum(DataSyncTask.total_records)).scalar() or 0

            return {
                'total_count': total_count,
                'success_count': success_count,
                'failed_count': failed_count,
                'running_count': running_count,
                'success_rate': success_count / total_count * 100 if total_count > 0 else 0,
                'total_records': total_records
            }