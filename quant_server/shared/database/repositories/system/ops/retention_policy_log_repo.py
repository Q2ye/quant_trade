# quant_server/shared/database/repositories/system/ops/retention_policy_log_repo.py
"""
保留策略执行日志Repository
负责RetentionPolicyLog表的数据访问操作

继承自BaseRepository，提供保留策略执行日志的管理功能
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.system_models import RetentionPolicyLog
from shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class RetentionPolicyLogRepository(BaseRepository[RetentionPolicyLog]):
    """
    保留策略执行日志Repository
    继承自BaseRepository，提供保留策略执行日志的数据访问方法
    """

    def __init__(self, session: AsyncSession):
        """
        初始化保留策略执行日志Repository

        Args:
            session: 数据库会话
        """
        super().__init__(session, RetentionPolicyLog)

    async def create_log (
            self,
            policy_id: str,
            execution_time: datetime,
            execution_status: str,
            dry_run: bool = False,
            rows_affected: int = 0,
            space_reclaimed: Optional[str] = None,
            error_message: Optional[str] = None,
            execution_details: Optional[Dict[str, Any]] = None
    ) -> RetentionPolicyLog:
        """
        创建执行日志

        Args:
            policy_id: 策略ID
            execution_time: 执行时间
            execution_status: 执行状态（success, failed）
            dry_run: 是否试运行
            rows_affected: 影响行数
            space_reclaimed: 回收空间
            error_message: 错误信息
            execution_details: 执行详情

        Returns:
            RetentionPolicyLog: 创建的日志对象
        """
        try:
            log_data = {
                'policy_id': policy_id,
                'execution_time': execution_time,
                'dry_run': dry_run,
                'rows_affected': rows_affected,
                'space_reclaimed': space_reclaimed,
                'execution_status': execution_status,
                'error_message': error_message,
                'execution_details': execution_details or {}
            }

            return await self.create(log_data)
        except Exception as e:
            raise RepositoryError(f"创建执行日志失败: {str(e)}")

    async def get_policy_logs (
            self,
            policy_id: str,
            limit: int = 100,
            offset: int = 0
    ) -> List[RetentionPolicyLog]:
        """
        获取指定策略的执行日志

        Args:
            policy_id: 策略ID
            limit: 限制记录数
            offset: 偏移量

        Returns:
            List[RetentionPolicyLog]: 执行日志列表
        """
        try:
            query = select(self.model).where(
                self.model.policy_id == policy_id
            ).order_by(
                desc(self.model.execution_time)
            ).offset(offset).limit(limit)

            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise RepositoryError(f"获取策略执行日志失败: {str(e)}")

    async def get_recent_logs (
            self,
            days: int = 7,
            limit: int = 100
    ) -> List[RetentionPolicyLog]:
        """
        获取最近N天的执行日志

        Args:
            days: 天数
            limit: 限制记录数

        Returns:
            List[RetentionPolicyLog]: 最近执行日志列表
        """
        try:
            from datetime import timedelta
            
            start_date = datetime.now() - timedelta(days=days)
            
            query = select(self.model).where(
                self.model.execution_time >= start_date
            ).order_by(
                desc(self.model.execution_time)
            ).limit(limit)

            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            raise RepositoryError(f"获取最近执行日志失败: {str(e)}")

    async def get_logs_by_status (
            self,
            execution_status: str,
            limit: int = 100
    ) -> List[RetentionPolicyLog]:
        """
        按执行状态获取日志

        Args:
            execution_status: 执行状态
            limit: 限制记录数

        Returns:
            List[RetentionPolicyLog]: 执行日志列表
        """
        try:
            return await self.get_many(
                execution_status=execution_status,
                limit=limit
            )
        except Exception as e:
            raise RepositoryError(f"按状态获取执行日志失败: {str(e)}")

    async def get_policy_statistics (
            self,
            policy_id: str,
            days: int = 30
    ) -> Dict[str, Any]:
        """
        获取策略执行统计

        Args:
            policy_id: 策略ID
            days: 统计天数

        Returns:
            Dict[str, Any]: 统计信息
        """
        try:
            from datetime import timedelta
            
            start_date = datetime.now() - timedelta(days=days)
            
            # 查询总执行次数
            total_query = select(func.count(self.model.id)).where(
                and_(
                    self.model.policy_id == policy_id,
                    self.model.execution_time >= start_date
                )
            )
            
            # 查询成功执行次数
            success_query = select(func.count(self.model.id)).where(
                and_(
                    self.model.policy_id == policy_id,
                    self.model.execution_time >= start_date,
                    self.model.execution_status == 'success'
                )
            )
            
            # 查询总清理行数
            rows_query = select(func.sum(self.model.rows_affected)).where(
                and_(
                    self.model.policy_id == policy_id,
                    self.model.execution_time >= start_date,
                    self.model.execution_status == 'success'
                )
            )
            
            total_result = await self.session.execute(total_query)
            success_result = await self.session.execute(success_query)
            rows_result = await self.session.execute(rows_query)
            
            total_count = total_result.scalar() or 0
            success_count = success_result.scalar() or 0
            total_rows = rows_result.scalar() or 0
            
            return {
                'policy_id': policy_id,
                'time_range': f'last_{days}_days',
                'total_executions': total_count,
                'successful_executions': success_count,
                'failed_executions': total_count - success_count,
                'success_rate': (success_count / total_count * 100) if total_count > 0 else 0,
                'total_rows_cleaned': total_rows,
                'average_rows_per_execution': (total_rows / success_count) if success_count > 0 else 0
            }
        except Exception as e:
            raise RepositoryError(f"获取策略统计失败: {str(e)}")

    async def cleanup_old_logs (
            self,
            retention_days: int = 90
    ) -> int:
        """
        清理旧的执行日志

        Args:
            retention_days: 保留天数

        Returns:
            int: 清理的日志数量
        """
        try:
            from datetime import timedelta
            from sqlalchemy import delete
            
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            delete_query = delete(self.model).where(
                self.model.execution_time < cutoff_date
            )
            
            result = await self.session.execute(delete_query) # type: ignore
            await self.session.flush()
            
            return result.rowcount or 0
        except Exception as e:
            raise RepositoryError(f"清理旧日志失败: {str(e)}")

    async def get_log_summary (
            self,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        获取日志汇总统计

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            Dict[str, Any]: 汇总统计
        """
        try:
            conditions = []
            
            if start_date:
                conditions.append(self.model.execution_time >= start_date)
            if end_date:
                conditions.append(self.model.execution_time <= end_date)
            
            # 查询总执行次数
            total_query = select(func.count(self.model.id))
            
            # 查询成功次数
            success_query = select(func.count(self.model.id)).where(
                self.model.execution_status == 'success'
            )
            
            # 查询总清理行数
            rows_query = select(func.sum(self.model.rows_affected)).where(
                self.model.execution_status == 'success'
            )
            
            if conditions:
                total_query = total_query.where(and_(*conditions))
                success_query = success_query.where(and_(*conditions))
                rows_query = rows_query.where(and_(*conditions))
            
            total_result = await self.session.execute(total_query)
            success_result = await self.session.execute(success_query)
            rows_result = await self.session.execute(rows_query)
            
            total_count = total_result.scalar() or 0
            success_count = success_result.scalar() or 0
            total_rows = rows_result.scalar() or 0
            
            return {
                'time_range': {
                    'start': start_date,
                    'end': end_date
                },
                'total_executions': total_count,
                'successful_executions': success_count,
                'failed_executions': total_count - success_count,
                'success_rate': (success_count / total_count * 100) if total_count > 0 else 0,
                'total_rows_cleaned': total_rows,
                'average_rows_per_execution': (total_rows / success_count) if success_count > 0 else 0
            }
        except Exception as e:
            raise RepositoryError(f"获取日志汇总失败: {str(e)}")