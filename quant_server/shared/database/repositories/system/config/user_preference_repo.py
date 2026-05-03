# -*- coding: utf-8 -*-
"""
用户偏好设置表Repository
位置：shared/database/repositories/system/user_preference_repo.py
"""
from typing import Optional, List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.system_models import UserPreference
from shared.database.repositories.base import BaseRepository
from shared.database.repositories.types import (
	RepositoryError
)


class UserPreferenceRepository(BaseRepository[UserPreference]):
	"""用户偏好设置Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, UserPreference)

	async def get_by_user_id (self, user_id: str) -> Optional[UserPreference]:
		"""
		根据用户ID获取偏好设置

		Args:
			user_id: 用户ID

		Returns:
			用户偏好设置对象或None
		"""
		try:
			query = select(self.model).where(
				self.model.user_id == user_id
			)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取用户偏好失败: {str(e)}")

	async def get_by_user_ids (self, user_ids: List[str]) -> List[UserPreference]:
		"""
		批量获取用户偏好设置

		Args:
			user_ids: 用户ID列表

		Returns:
			用户偏好设置列表
		"""
		try:
			query = select(self.model).where(
				self.model.user_id.in_(user_ids)
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"批量获取用户偏好失败: {str(e)}")

	async def update_language (self, user_id: str, language: str) -> Optional[UserPreference]:
		"""
		更新用户语言设置

		Args:
			user_id: 用户ID
			language: 语言代码

		Returns:
			更新后的用户偏好设置
		"""
		try:
			preference = await self.get_by_user_id(user_id)
			if preference:
				return await self.update(preference.id, {"language": language})
			return None
		except Exception as e:
			raise RepositoryError(f"更新语言设置失败: {str(e)}")

	async def update_theme (self, user_id: str, theme: str) -> Optional[UserPreference]:
		"""
		更新用户主题设置

		Args:
			user_id: 用户ID
			theme: 主题（light/dark）

		Returns:
			更新后的用户偏好设置
		"""
		try:
			preference = await self.get_by_user_id(user_id)
			if preference:
				return await self.update(preference.id, {"theme": theme})
			return None
		except Exception as e:
			raise RepositoryError(f"更新主题设置失败: {str(e)}")

	async def update_timezone (self, user_id: str, timezone: str) -> Optional[UserPreference]:
		"""
		更新用户时区设置

		Args:
			user_id: 用户ID
			timezone: 时区

		Returns:
			更新后的用户偏好设置
		"""
		try:
			preference = await self.get_by_user_id(user_id)
			if preference:
				return await self.update(preference.id, {"timezone": timezone})
			return None
		except Exception as e:
			raise RepositoryError(f"更新时区设置失败: {str(e)}")

	async def update_notification_settings (self, user_id: str, settings: Dict[str, Any]) -> Optional[UserPreference]:
		"""
		更新用户通知设置

		Args:
			user_id: 用户ID
			settings: 通知设置字典

		Returns:
			更新后的用户偏好设置
		"""
		try:
			preference = await self.get_by_user_id(user_id)
			if preference:
				return await self.update(preference.id, {"notification_settings": settings})
			return None
		except Exception as e:
			raise RepositoryError(f"更新通知设置失败: {str(e)}")

	async def update_trading_settings (self, user_id: str, settings: Dict[str, Any]) -> Optional[UserPreference]:
		"""
		更新用户交易设置

		Args:
			user_id: 用户ID
			settings: 交易设置字典

		Returns:
			更新后的用户偏好设置
		"""
		try:
			preference = await self.get_by_user_id(user_id)
			if preference:
				return await self.update(preference.id, {"trading_settings": settings})
			return None
		except Exception as e:
			raise RepositoryError(f"更新交易设置失败: {str(e)}")

	async def update_display_settings (self, user_id: str, settings: Dict[str, Any]) -> Optional[UserPreference]:
		"""
		更新用户显示设置

		Args:
			user_id: 用户ID
			settings: 显示设置字典

		Returns:
			更新后的用户偏好设置
		"""
		try:
			preference = await self.get_by_user_id(user_id)
			if preference:
				return await self.update(preference.id, {"display_settings": settings})
			return None
		except Exception as e:
			raise RepositoryError(f"更新显示设置失败: {str(e)}")

	async def get_users_by_theme (self, theme: str) -> List[UserPreference]:
		"""
		获取使用指定主题的用户偏好

		Args:
			theme: 主题名称

		Returns:
			用户偏好设置列表
		"""
		try:
			query = select(self.model).where(
				self.model.theme == theme
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取主题用户失败: {str(e)}")

	async def get_users_by_language (self, language: str) -> List[UserPreference]:
		"""
		获取使用指定语言的用户偏好

		Args:
			language: 语言代码

		Returns:
			用户偏好设置列表
		"""
		try:
			query = select(self.model).where(
				self.model.language == language
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取语言用户失败: {str(e)}")

	async def get_users_by_timezone (self, timezone: str) -> List[UserPreference]:
		"""
		获取使用指定时区的用户偏好

		Args:
			timezone: 时区

		Returns:
			用户偏好设置列表
		"""
		try:
			query = select(self.model).where(
				self.model.timezone == timezone
			)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取时区用户失败: {str(e)}")

	async def initialize_user_preference (self, user_id: str) -> UserPreference:
		"""
		初始化用户偏好设置（创建默认设置）

		Args:
			user_id: 用户ID

		Returns:
			创建的用户偏好设置
		"""
		try:
			# 检查是否已存在
			existing = await self.get_by_user_id(user_id)
			if existing:
				return existing

			# 创建默认设置
			data = {
				"user_id": user_id,
				"language": "zh-CN",
				"timezone": "Asia/Shanghai",
				"theme": "light",
				"notification_settings": {"email": True, "wechat": False, "sms": False},
				"trading_settings": {"default_account": None, "confirm_before_trade": True},
				"display_settings": {"default_chart_type": "candle", "show_grid": True}
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"初始化用户偏好失败: {str(e)}")
