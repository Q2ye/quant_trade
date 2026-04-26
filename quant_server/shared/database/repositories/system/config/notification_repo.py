# quant_server/shared/database/repositories/system/notification_repo.py
"""
系统通知Repository
位置：shared/database/repositories/system/notification_repo.py
"""
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.system_models import SystemNotification
from quant_server.shared.database.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
	"""
	系统通知仓库
	用于管理系统通知的创建、发送、查询和管理
	"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, SystemNotification)

	async def create_notification (
			self,
			notification_data: Dict[str, Any]
	) -> SystemNotification:
		"""
		创建通知记录

		Args:
			notification_data: 通知数据

		Returns:
			SystemNotification: 创建的通知记录
		"""
		try:
			# 创建通知记录
			notification = SystemNotification(
				notification_type=notification_data.get("notification_type", "SYSTEM"),
				title=notification_data.get("title", ""),
				content=notification_data.get("content", ""),
				priority=notification_data.get("priority", "normal"),
				recipient_id=notification_data.get("recipient_id"),
				recipient_type=notification_data.get("recipient_type", "USER"),
				action_url=notification_data.get("action_url"),
				metainfo=notification_data.get("metainfo"),
				expiry_at=notification_data.get("expiry_at")
			)

			self.session.add(notification)
			await self.session.commit()
			await self.session.refresh(notification)

			return notification
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"创建通知失败: {str(e)}")

	async def get_user_notifications (
			self,
			user_id: str,
			unread_only: bool = False,
			limit: int = 50,
			offset: int = 0
	) -> Dict[str, Any]:
		"""
		获取用户通知

		Args:
			user_id: 用户ID
			unread_only: 是否只获取未读通知
			limit: 每页数量
			offset: 偏移量

		Returns:
			Dict: 包含通知列表和总数的字典
		"""
		try:
			# 构建查询条件
			query = select(SystemNotification).where(
				SystemNotification.recipient_id == user_id
			)

			if unread_only:
				query = query.where(SystemNotification.is_read == False)

			# 获取总数
			total_query = select(func.count()).select_from(query.subquery())
			total_result = await self.session.execute(total_query)
			total = total_result.scalar() or 0

			# 获取未读数量
			unread_query = select(func.count()).where(
				and_(
					SystemNotification.recipient_id == user_id,
					SystemNotification.is_read == False
				)
			)
			unread_result = await self.session.execute(unread_query)
			unread_count = unread_result.scalar() or 0

			# 获取分页数据
			query = query.order_by(desc(SystemNotification.created_at)).offset(offset).limit(limit)
			result = await self.session.execute(query)
			notifications = result.scalars().all()

			return {
				"notifications": notifications,
				"total": total,
				"unread_count": unread_count,
				"offset": offset,
				"limit": limit
			}
		except Exception as e:
			raise Exception(f"获取用户通知失败: {str(e)}")

	async def get_notification_by_id (
			self,
			notification_id: str
	) -> Optional[SystemNotification]:
		"""
		根据ID获取通知

		Args:
			notification_id: 通知ID

		Returns:
			Optional[SystemNotification]: 通知信息，如果不存在返回None
		"""
		try:
			query = select(SystemNotification).where(SystemNotification.id == notification_id)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise Exception(f"获取通知失败: {str(e)}")

	async def mark_as_read (
			self,
			notification_id: str,
			user_id: str
	) -> bool:
		"""
		标记通知为已读

		Args:
			notification_id: 通知ID
			user_id: 用户ID

		Returns:
			bool: 是否成功标记
		"""
		try:
			# 获取通知记录
			notification = await self.get_notification_by_id(notification_id)
			if not notification:
				return False

			# 检查权限：只有接收者才能标记为已读
			if notification.recipient_id != user_id:
				return False

			# 标记为已读
			if not notification.is_read:
				notification.is_read = True
				notification.read_at = datetime.now()
				await self.session.commit()

			return True
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"标记通知为已读失败: {str(e)}")

	async def mark_all_as_read (self, user_id: str) -> int:
		"""
		标记用户所有通知为已读

		Args:
			user_id: 用户ID

		Returns:
			int: 标记的通知数量
		"""
		try:
			# 获取用户所有未读通知
			query = select(SystemNotification).where(
				and_(
					SystemNotification.recipient_id == user_id,
					SystemNotification.is_read == False
				)
			)
			result = await self.session.execute(query)
			notifications = result.scalars().all()

			# 批量标记为已读
			count = 0
			for notification in notifications:
				notification.is_read = True
				notification.read_at = datetime.now()
				count += 1

			if count > 0:
				await self.session.commit()

			return count
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"标记所有通知为已读失败: {str(e)}")

	async def send_notification (
			self,
			user_id: str,
			notification_type: str,
			title: str,
			content: str,
			priority: str = "normal",
			action_url: Optional[str] = None,
			metainfo: Optional[Dict[str, Any]] = None,
			expires_at: Optional[datetime] = None
	) -> SystemNotification:
		"""
		发送通知

		Args:
			user_id: 用户ID
			notification_type: 通知类型
			title: 标题
			content: 内容
			priority: 优先级（critical/high/normal/low）
			action_url: 操作链接
			metainfo: 元数据
			expires_at: 过期时间

		Returns:
			SystemNotification: 发送的通知信息
		"""
		try:
			notification_data = {
				"recipient_id": user_id,
				"notification_type": notification_type,
				"title": title,
				"content": content,
				"priority": priority,
				"action_url": action_url,
				"metainfo": metainfo,
				"expiry_at": expires_at
			}

			return await self.create_notification(notification_data)
		except Exception as e:
			raise Exception(f"发送通知失败: {str(e)}")

	async def batch_send_notification (
			self,
			user_ids: List[str],
			notification_type: str,
			title: str,
			content: str,
			priority: str = "normal",
			action_url: Optional[str] = None,
			metainfo: Optional[Dict[str, Any]] = None,
			expires_at: Optional[datetime] = None
	) -> int:
		"""
		批量发送通知

		Args:
			user_ids: 用户ID列表
			notification_type: 通知类型
			title: 标题
			content: 内容
			priority: 优先级
			action_url: 操作链接
			metainfo: 元数据
			expires_at: 过期时间

		Returns:
			int: 成功发送的数量
		"""
		try:
			success_count = 0
			for user_id in user_ids:
				try:
					await self.send_notification(
						user_id=user_id,
						notification_type=notification_type,
						title=title,
						content=content,
						priority=priority,
						action_url=action_url,
						metainfo=metainfo,
						expires_at=expires_at
					)
					success_count += 1
				except (ValueError, TypeError):
					continue

			return success_count
		except Exception as e:
			raise Exception(f"批量发送通知失败: {str(e)}")

	async def search_notifications (
			self,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			user_id: Optional[str] = None,
			notification_type: Optional[str] = None,
			priority: Optional[str] = None,
			is_read: Optional[bool] = None,
			limit: int = 100,
			offset: int = 0
	) -> Dict[str, Any]:
		"""
		搜索通知记录

		Args:
			start_date: 开始日期
			end_date: 结束日期
			user_id: 用户ID
			notification_type: 通知类型
			priority: 优先级
			is_read: 是否已读
			limit: 每页数量
			offset: 偏移量

		Returns:
			Dict[str, Any]: 包含通知列表和总数的字典
		"""
		try:
			# 构建查询条件
			query = select(SystemNotification)

			# 添加过滤条件
			if start_date:
				query = query.where(SystemNotification.created_at >= start_date)
			if end_date:
				query = query.where(SystemNotification.created_at <= end_date)
			if user_id:
				query = query.where(SystemNotification.recipient_id == user_id)
			if notification_type:
				query = query.where(SystemNotification.notification_type == notification_type)
			if priority:
				query = query.where(SystemNotification.priority == priority)
			if is_read is not None:
				query = query.where(SystemNotification.is_read == is_read)

			# 获取总数
			total_query = select(func.count()).select_from(query.subquery())
			total_result = await self.session.execute(total_query)
			total = total_result.scalar() or 0

			# 获取分页数据
			query = query.order_by(desc(SystemNotification.created_at)).offset(offset).limit(limit)
			result = await self.session.execute(query)
			notifications = result.scalars().all()

			return {
				"notifications": notifications,
				"total": total,
				"offset": offset,
				"limit": limit
			}
		except Exception as e:
			raise Exception(f"搜索通知记录失败: {str(e)}")

	async def get_notification_statistics (
			self,
			start_date: datetime,
			end_date: datetime
	) -> Dict[str, Any]:
		"""
		获取通知统计信息

		Args:
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Dict[str, Any]: 统计信息
		"""
		try:
			# 总通知数
			total_query = select(func.count()).where(
				and_(
					SystemNotification.created_at >= start_date,
					SystemNotification.created_at <= end_date
				)
			)
			total_result = await self.session.execute(total_query)
			total_sent = total_result.scalar() or 0

			# 已读通知数
			read_query = select(func.count()).where(
				and_(
					SystemNotification.created_at >= start_date,
					SystemNotification.created_at <= end_date,
					SystemNotification.is_read == True
				)
			)
			read_result = await self.session.execute(read_query)
			total_read = read_result.scalar() or 0

			# 按类型统计
			type_query = select(
				SystemNotification.notification_type,
				func.count()
			).where(
				and_(
					SystemNotification.created_at >= start_date,
					SystemNotification.created_at <= end_date
				)
			).group_by(SystemNotification.notification_type)
			type_result = await self.session.execute(type_query)
			by_type = {row[0]: row[1] for row in type_result.all()}

			# 按优先级统计
			priority_query = select(
				SystemNotification.priority,
				func.count()
			).where(
				and_(
					SystemNotification.created_at >= start_date,
					SystemNotification.created_at <= end_date
				)
			).group_by(SystemNotification.priority)
			priority_result = await self.session.execute(priority_query)
			by_priority = {row[0]: row[1] for row in priority_result.all()}

			# 计算阅读率
			read_rate = (total_read / total_sent * 100) if total_sent > 0 else 0

			return {
				"total_sent": total_sent,
				"total_read": total_read,
				"read_rate": round(read_rate, 2),
				"by_type": by_type,
				"by_priority": by_priority,
				"date_range": {
					"start": start_date,
					"end": end_date
				}
			}
		except Exception as e:
			raise Exception(f"获取通知统计信息失败: {str(e)}")

	async def clean_expired_notifications (self) -> int:
		"""
		清理过期的通知

		Returns:
			int: 清理的通知数量
		"""
		try:
			# 获取当前时间
			current_time = datetime.now()

			# 查询过期通知
			query = select(SystemNotification).where(
				and_(
					SystemNotification.expiry_at.isnot(None),
					SystemNotification.expiry_at < current_time
				)
			)
			result = await self.session.execute(query)
			expired_notifications = result.scalars().all()

			# 删除过期通知
			count = 0
			for notification in expired_notifications:
				await self.session.delete(notification)
				count += 1

			if count > 0:
				await self.session.commit()

			return count
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"清理过期通知失败: {str(e)}")

	async def delete_notification (self, notification_id: str) -> bool:
		"""
		删除通知

		Args:
			notification_id: 通知ID

		Returns:
			bool: 是否成功删除
		"""
		try:
			# 获取通知记录
			notification = await self.get_notification_by_id(notification_id)
			if not notification:
				return False

			# 删除通知
			await self.session.delete(notification)
			await self.session.commit()

			return True
		except Exception as e:
			await self.session.rollback()
			raise Exception(f"删除通知失败: {str(e)}")