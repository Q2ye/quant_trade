# quant_server/shared/database/repositories/analysis/monitor/alert_delivery_log_repo.py
"""
报警发送日志Repository
负责AlertDeliveryLog表的数据访问操作

继承自BaseRepository，提供报警发送日志的记录和查询功能
包括发送状态跟踪、失败重试、渠道统计等
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, delete, and_, func, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import AlertDeliveryLog
from shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


class AlertDeliveryLogRepository(BaseRepository[AlertDeliveryLog]):
	"""
	报警发送日志Repository
	继承自BaseRepository，提供报警发送日志的数据访问方法
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化报警发送日志Repository

		Args:
			session: 数据库会话
		"""
		super().__init__(session, AlertDeliveryLog)

	async def create_delivery_log (
			self,
			alert_id: str,
			channel: str,
			recipient: str,
			status: str = "pending",
			error_message: Optional[str] = None
	) -> AlertDeliveryLog:
		"""
		创建报警发送日志

		Args:
			alert_id: 报警ID
			channel: 发送渠道（email/wechat/dingtalk/sms）
			recipient: 接收者
			status: 发送状态（pending, sent, failed, delivered）
			error_message: 错误信息（可选）

		Returns:
			AlertDeliveryLog: 创建的发送日志对象
		"""
		try:
			log_data = {
				'alert_id': alert_id,
				'channel': channel,
				'recipient': recipient,
				'status': status,
				'error_message': error_message,
				'retry_count': 0
			}

			return await self.create(log_data)
		except Exception as e:
			raise RepositoryError(f"创建发送日志失败: {str(e)}")

	async def create_batch_delivery_logs (
			self,
			alert_id: str,
			channels: List[str],
			recipients: List[str],
			status: str = "pending"
	) -> List[AlertDeliveryLog]:
		"""
		批量创建发送日志

		Args:
			alert_id: 报警ID
			channels: 发送渠道列表
			recipients: 接收者列表
			status: 发送状态

		Returns:
			List[AlertDeliveryLog]: 创建的发送日志对象列表
		"""
		try:
			logs = []

			for channel, recipient in zip(channels, recipients):
				log_data = {
					'alert_id': alert_id,
					'channel': channel,
					'recipient': recipient,
					'status': status,
					'retry_count': 0
				}
				logs.append(log_data)

			return await self.batch_create(logs)
		except Exception as e:
			raise RepositoryError(f"批量创建发送日志失败: {str(e)}")

	async def update_delivery_status (
			self,
			log_id: str,
			status: str,
			error_message: Optional[str] = None,
			increment_retry: bool = False
	) -> bool:
		"""
		更新发送状态

		Args:
			log_id: 日志ID
			status: 新状态（sent, failed, delivered）
			error_message: 错误信息（可选）
			increment_retry: 是否增加重试计数

		Returns:
			bool: 更新是否成功
		"""
		try:
			update_data = {'status': status}

			if status == 'sent':
				update_data['sent_at'] = datetime.now().isoformat()
			elif status == 'delivered':
				update_data['delivered_at'] = datetime.now().isoformat()

			if error_message:
				update_data['error_message'] = error_message

			if increment_retry:
				# 获取当前重试计数
				query = select(self.model.retry_count).where(self.model.id == log_id)
				result = await self.session.execute(query)
				current_retry = result.scalar() or 0
				update_data['retry_count'] = current_retry + 1

			return await self.update(log_id, update_data) is not None
		except Exception as e:
			raise RepositoryError(f"更新发送状态失败: {str(e)}")

	async def mark_as_sent (
			self,
			log_id: str,
			error_message: Optional[str] = None
	) -> bool:
		"""
		标记为已发送

		Args:
			log_id: 日志ID
			error_message: 错误信息（可选）

		Returns:
			bool: 标记是否成功
		"""
		return await self.update_delivery_status(log_id, 'sent', error_message)

	async def mark_as_failed (
			self,
			log_id: str,
			error_message: str,
			increment_retry: bool = True
	) -> bool:
		"""
		标记为发送失败

		Args:
			log_id: 日志ID
			error_message: 错误信息
			increment_retry: 是否增加重试计数

		Returns:
			bool: 标记是否成功
		"""
		return await self.update_delivery_status(
			log_id, 'failed', error_message, increment_retry
		)

	async def mark_as_delivered (
			self,
			log_id: str,
			error_message: Optional[str] = None
	) -> bool:
		"""
		标记为已送达

		Args:
			log_id: 日志ID
			error_message: 错误信息（可选）

		Returns:
			bool: 标记是否成功
		"""
		return await self.update_delivery_status(log_id, 'delivered', error_message)

	async def get_pending_logs (
			self,
			alert_id: Optional[str] = None,
			channel: Optional[str] = None,
			limit: int = 100
	) -> List[AlertDeliveryLog]:
		"""
		获取待处理的发送日志

		Args:
			alert_id: 报警ID过滤（可选）
			channel: 渠道过滤（可选）
			limit: 限制记录数

		Returns:
			List[AlertDeliveryLog]: 待处理日志列表
		"""
		try:
			filters = {'status': 'pending'}

			if alert_id:
				filters['alert_id'] = alert_id
			if channel:
				filters['channel'] = channel

			return await self.get_many(limit=limit, **filters)
		except Exception as e:
			raise RepositoryError(f"获取待处理日志失败: {str(e)}")

	async def get_failed_logs (
			self,
			max_retries: int = 3,
			hours: int = 24,
			limit: int = 100
	) -> List[AlertDeliveryLog]:
		"""
		获取失败的发送日志（可用于重试）

		Args:
			max_retries: 最大重试次数
			hours: 时间范围（小时）
			limit: 限制记录数

		Returns:
			List[AlertDeliveryLog]: 失败日志列表
		"""
		try:
			time_threshold = datetime.now() - timedelta(hours=hours)

			query = select(self.model).where(
				and_(
					self.model.status == 'failed',
					self.model.retry_count < max_retries,
					self.model.created_at >= time_threshold
				)
			).order_by(asc(self.model.created_at)).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取失败日志失败: {str(e)}")

	async def get_logs_by_alert (
			self,
			alert_id: str,
			include_resolved: bool = True
	) -> List[AlertDeliveryLog]:
		"""
		获取指定报警的所有发送日志

		Args:
			alert_id: 报警ID
			include_resolved: 是否包含已解决的日志

		Returns:
			List[AlertDeliveryLog]: 发送日志列表
		"""
		try:
			if not include_resolved:
				# 使用自定义查询获取非已解决状态的日志
				query = select(self.model).where(
					and_(
						self.model.alert_id == alert_id,
						self.model.status.in_(['pending', 'sent', 'failed'])
					)
				)
				result = await self.session.execute(query)
				return result.scalars().all()
			else:
				return await self.get_all(alert_id=alert_id)
		except Exception as e:
			raise RepositoryError(f"获取报警日志失败: {str(e)}")

	async def get_delivery_summary_by_alert (
			self,
			alert_id: str
	) -> Dict[str, Any]:
		"""
		获取报警的发送摘要

		Args:
			alert_id: 报警ID

		Returns:
			Dict[str, Any]: 发送摘要信息
		"""
		try:
			query = select(
				self.model.channel,
				self.model.status,
				func.count(self.model.id).label('count')
			).where(
				self.model.alert_id == alert_id
			).group_by(
				self.model.channel,
				self.model.status
			)

			result = await self.session.execute(query)

			summary: Dict[str, Any] = {
				'total': 0,
				'by_channel': {},
				'by_status': {'pending': 0, 'sent': 0, 'failed': 0, 'delivered': 0}
			}

			for row in result.all():
				channel = row.channel
				status = row.status
				count = row.count
				if channel not in summary['by_channel']:
					summary['by_channel'][channel] = {
						'pending': 0, 'sent': 0, 'failed': 0, 'delivered': 0, 'total': 0
					}

				summary['by_channel'][channel][status] = count
				summary['by_channel'][channel]['total'] += count
				summary['by_status'][status] += count
				summary['total'] += count

			return summary
		except Exception as e:
			raise RepositoryError(f"获取发送摘要失败: {str(e)}")

	async def get_channel_statistics (
			self,
			hours: Optional[int] = None,
			channel: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取渠道发送统计

		Args:
			hours: 时间范围（小时，可选）
			channel: 渠道过滤（可选）

		Returns:
			Dict[str, Any]: 渠道统计信息
		"""
		try:
			query = select(
				self.model.channel,
				self.model.status,
				func.count(self.model.id).label('count'),
				func.avg(
					func.extract('epoch', self.model.delivered_at - self.model.sent_at)
				).label('avg_delivery_time')
			)

			if hours:
				time_threshold = datetime.now() - timedelta(hours=hours)
				query = query.where(self.model.created_at >= time_threshold)

			if channel:
				query = query.where(self.model.channel == channel)

			query = query.group_by(self.model.channel, self.model.status)

			result = await self.session.execute(query)

			stats = {
				'total': 0,
				'success_rate': 0,
				'by_channel': {}
			}

			total_success = 0
			total_failed = 0

			for ch, status, count, avg_time in result.all():
				if ch not in stats['by_channel']:
					stats['by_channel'][ch] = {
						'total': 0,
						'success': 0,
						'failed': 0,
						'pending': 0,
						'avg_delivery_time': 0
					}

				stats['by_channel'][ch]['total'] += count

				if status == 'delivered':
					stats['by_channel'][ch]['success'] += count
					total_success += count
					if avg_time:
						stats['by_channel'][ch]['avg_delivery_time'] = float(avg_time)
				elif status == 'failed':
					stats['by_channel'][ch]['failed'] += count
					total_failed += count
				elif status == 'pending':
					stats['by_channel'][ch]['pending'] += count

				stats['total'] += count

			if stats['total'] > 0:
				stats['success_rate'] = (total_success / stats['total']) * 100
				stats['failure_rate'] = (total_failed / stats['total']) * 100

			return stats
		except Exception as e:
			raise RepositoryError(f"获取渠道统计失败: {str(e)}")

	async def get_failure_analysis (
			self,
			days: int = 7,
			limit: int = 20
	) -> List[Dict[str, Any]]:
		"""
		获取失败分析

		Args:
			days: 分析天数
			limit: 限制记录数

		Returns:
			List[Dict[str, Any]]: 失败分析结果
		"""
		try:
			time_threshold = datetime.now() - timedelta(days=days)

			query = select(
				self.model.channel,
				self.model.error_message,
				func.count(self.model.id).label('failure_count'),
				func.max(self.model.created_at).label('last_failure')
			).where(
				and_(
					self.model.status == 'failed',
					self.model.created_at >= time_threshold,
					self.model.error_message.isnot(None)
				)
			).group_by(
				self.model.channel,
				self.model.error_message
			).order_by(
				desc(func.count(self.model.id))
			).limit(limit)

			result = await self.session.execute(query)

			analysis = []
			for channel, error_message, count, last_failure in result.all():
				analysis.append({
					'channel': channel,
					'error_message': error_message[:200] if error_message else 'Unknown error',
					'failure_count': count,
					'last_failure': last_failure,
					'error_category': AlertDeliveryLogRepository._categorize_error(error_message)
				})

			return analysis
		except Exception as e:
			raise RepositoryError(f"获取失败分析失败: {str(e)}")

	@staticmethod
	def _categorize_error (error_message: Optional[str]) -> str:
		"""
		对错误信息进行分类

		Args:
			error_message: 错误信息

		Returns:
			str: 错误分类
		"""
		if not error_message:
			return 'unknown'

		error_lower = error_message.lower()

		if 'network' in error_lower or 'connection' in error_lower or 'timeout' in error_lower:
			return 'network'
		elif 'authentication' in error_lower or 'auth' in error_lower or 'password' in error_lower:
			return 'authentication'
		elif 'quota' in error_lower or 'limit' in error_lower or 'rate limit' in error_lower:
			return 'quota'
		elif 'format' in error_lower or 'invalid' in error_lower or 'parse' in error_lower:
			return 'format'
		elif 'address' in error_lower or 'recipient' in error_lower or 'user' in error_lower:
			return 'recipient'
		else:
			return 'other'

	async def cleanup_old_logs (
			self,
			days: int = 90,
			keep_failed: bool = True
	) -> int:
		"""
		清理旧的发送日志

		Args:
			days: 保留天数
			keep_failed: 是否保留失败日志

		Returns:
			int: 删除的记录数
		"""
		try:
			time_threshold = datetime.now() - timedelta(days=days)

			conditions = [self.model.created_at < time_threshold]

			if keep_failed:
				# 只删除已送达的日志
				conditions.append(self.model.status == 'delivered')

			query = delete(self.model).where(and_(*conditions))

			result = await self.session.execute(query) # type: ignore[arg-type]
			await self.session.commit()

			return result.rowcount if result.rowcount is not None else 0
		except Exception as e:
			await self.session.rollback()
			raise RepositoryError(f"清理旧日志失败: {str(e)}")