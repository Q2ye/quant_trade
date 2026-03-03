# -*- coding: utf-8 -*-
"""
许可证密钥表Repository
位置：shared/database/repositories/system/license_key_repo.py
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, between
from sqlalchemy.orm import joinedload

from quant_server.shared.database.models.system_models import LicenseKey
from quant_server.shared.database.repositories import NotFoundError
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError


class LicenseKeyRepository(BaseRepository[LicenseKey]):
	"""许可证密钥Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, LicenseKey)

	async def get_by_license_key (self, license_key: str) -> Optional[LicenseKey]:
		"""
		根据许可证密钥获取记录

		Args:
			license_key: 许可证密钥

		Returns:
			许可证记录或None
		"""
		try:
			query = select(self.model).where(
				self.model.license_key == license_key
			)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取许可证记录失败: {str(e)}")

	async def get_by_user_id (self, user_id: int) -> Optional[LicenseKey]:
		"""
		根据用户ID获取许可证

		Args:
			user_id: 用户ID

		Returns:
			许可证记录或None
		"""
		try:
			query = select(self.model).where(
				self.model.user_id == user_id
			).order_by(
				desc(self.model.created_at)
			).limit(1)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取用户许可证失败: {str(e)}")

	async def get_active_licenses (
			self,
			license_type: Optional[str] = None,
			include_expired: bool = False
	) -> List[LicenseKey]:
		"""
		获取激活的许可证

		Args:
			license_type: 许可证类型
			include_expired: 是否包含已过期的

		Returns:
			许可证列表
		"""
		try:
			query = select(self.model).where(
				self.model.is_active == True
			)

			if license_type:
				query = query.where(self.model.license_type == license_type)

			if not include_expired:
				today = date.today()
				query = query.where(
					and_(
						self.model.valid_from <= today,
						self.model.valid_to >= today
					)
				)

			query = query.order_by(desc(self.model.created_at))

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取激活许可证失败: {str(e)}")

	async def get_expiring_licenses (
			self,
			days_threshold: int = 30
	) -> List[LicenseKey]:
		"""
		获取即将过期的许可证

		Args:
			days_threshold: 过期阈值（天）

		Returns:
			即将过期的许可证列表
		"""
		try:
			today = date.today()
			threshold_date = today + timedelta(days=days_threshold)

			query = select(self.model).where(
				and_(
					self.model.is_active == True,
					self.model.valid_to >= today,
					self.model.valid_to <= threshold_date
				)
			).order_by(
				asc(self.model.valid_to)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取即将过期许可证失败: {str(e)}")

	async def get_expired_licenses (self) -> List[LicenseKey]:
		"""
		获取已过期的许可证

		Returns:
			已过期的许可证列表
		"""
		try:
			today = date.today()

			query = select(self.model).where(
				and_(
					self.model.is_active == True,
					self.model.valid_to < today
				)
			).order_by(
				desc(self.model.valid_to)
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取已过期许可证失败: {str(e)}")

	async def create_license (
			self,
			license_key: str,
			license_type: str,
			user_id: Optional[int] = None,
			max_users: int = 1,
			max_strategies: int = 10,
			valid_from: Optional[date] = None,
			valid_to: Optional[date] = None,
			is_active: bool = True,
			metadata: Optional[Dict[str, Any]] = None
	) -> LicenseKey:
		"""
		创建许可证

		Args:
			license_key: 许可证密钥
			license_type: 许可证类型
			user_id: 用户ID
			max_users: 最大用户数
			max_strategies: 最大策略数
			valid_from: 有效期开始
			valid_to: 有效期结束
			is_active: 是否激活
			metadata: 元数据

		Returns:
			创建的许可证记录
		"""
		try:
			today = date.today()

			data = {
				"license_key": license_key,
				"license_type": license_type,
				"user_id": user_id,
				"max_users": max_users,
				"max_strategies": max_strategies,
				"valid_from": valid_from or today,
				"valid_to": valid_to or (today + timedelta(days=365)),
				"is_active": is_active,
				"activation_date": datetime.now() if is_active else None,
				"metadata": metadata or {}
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"创建许可证失败: {str(e)}")

	async def activate_license (self, license_key: str, user_id: Optional[int] = None) -> Optional[LicenseKey]:
		"""
		激活许可证

		Args:
			license_key: 许可证密钥
			user_id: 用户ID

		Returns:
			更新后的许可证记录
		"""
		try:
			license_record = await self.get_by_license_key(license_key)
			if not license_record:
				raise NotFoundError(f"许可证不存在: {license_key}")

			if not license_record.is_active:
				update_data = {
					"is_active": True,
					"activation_date": datetime.now(),
					"last_check_date": datetime.now()
				}

				if user_id:
					update_data["user_id"] = user_id

				return await self.update(license_record.id, update_data)

			return license_record
		except Exception as e:
			if isinstance(e, NotFoundError):
				raise e
			raise RepositoryError(f"激活许可证失败: {str(e)}")

	async def deactivate_license (self, license_key: str) -> Optional[LicenseKey]:
		"""
		停用许可证

		Args:
			license_key: 许可证密钥

		Returns:
			更新后的许可证记录
		"""
		try:
			license_record = await self.get_by_license_key(license_key)
			if not license_record:
				raise NotFoundError(f"许可证不存在: {license_key}")

			if license_record.is_active:
				return await self.update(license_record.id, {
					"is_active": False,
					"updated_at": datetime.now()
				})

			return license_record
		except Exception as e:
			if isinstance(e, NotFoundError):
				raise e
			raise RepositoryError(f"停用许可证失败: {str(e)}")

	async def update_last_check (self, license_key: str) -> Optional[LicenseKey]:
		"""
		更新许可证最后检查时间

		Args:
			license_key: 许可证密钥

		Returns:
			更新后的许可证记录
		"""
		try:
			license_record = await self.get_by_license_key(license_key)
			if not license_record:
				raise NotFoundError(f"许可证不存在: {license_key}")

			return await self.update(license_record.id, {
				"last_check_date": datetime.now()
			})
		except Exception as e:
			if isinstance(e, NotFoundError):
				raise e
			raise RepositoryError(f"更新许可证检查时间失败: {str(e)}")

	async def validate_license (
			self,
			license_key: str,
			user_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		验证许可证

		Args:
			license_key: 许可证密钥
			user_id: 用户ID（可选，用于验证用户绑定）

		Returns:
			验证结果
		"""
		try:
			license_record = await self.get_by_license_key(license_key)

			if not license_record:
				return {
					"valid": False,
					"error": "许可证不存在",
					"code": "LICENSE_NOT_FOUND"
				}

			today = date.today()
			validation_result = {
				"valid": True,
				"license_key": license_record.license_key,
				"license_type": license_record.license_type,
				"max_users": license_record.max_users,
				"max_strategies": license_record.max_strategies,
				"valid_from": license_record.valid_from,
				"valid_to": license_record.valid_to,
				"is_active": license_record.is_active,
				"metadata": license_record.metadata or {}
			}

			# 检查是否激活
			if not license_record.is_active:
				validation_result.update({
					"valid": False,
					"error": "许可证未激活",
					"code": "LICENSE_INACTIVE"
				})
				return validation_result

			# 检查有效期
			if license_record.valid_from > today:
				validation_result.update({
					"valid": False,
					"error": "许可证尚未生效",
					"code": "LICENSE_NOT_YET_VALID"
				})
				return validation_result

			if license_record.valid_to < today:
				validation_result.update({
					"valid": False,
					"error": "许可证已过期",
					"code": "LICENSE_EXPIRED"
				})
				return validation_result

			# 检查用户绑定
			if user_id and license_record.user_id and license_record.user_id != user_id:
				validation_result.update({
					"valid": False,
					"error": "许可证已绑定到其他用户",
					"code": "LICENSE_BOUND_TO_OTHER_USER"
				})
				return validation_result

			return validation_result
		except Exception as e:
			return {
				"valid": False,
				"error": f"验证许可证失败: {str(e)}",
				"code": "VALIDATION_ERROR"
			}

	async def get_license_statistics (self) -> Dict[str, Any]:
		"""
		获取许可证统计信息

		Returns:
			许可证统计
		"""
		try:
			today = date.today()

			# 总数统计
			total_query = select(func.count()).select_from(self.model)
			total_result = await self.session.execute(total_query)
			total = total_result.scalar() or 0

			# 激活数统计
			active_query = select(func.count()).where(self.model.is_active == True)
			active_result = await self.session.execute(active_query)
			active = active_result.scalar() or 0

			# 过期数统计
			expired_query = select(func.count()).where(
				and_(
					self.model.is_active == True,
					self.model.valid_to < today
				)
			)
			expired_result = await self.session.execute(expired_query)
			expired = expired_result.scalar() or 0

			# 即将过期数（30天内）
			expiring_threshold = today + timedelta(days=30)
			expiring_query = select(func.count()).where(
				and_(
					self.model.is_active == True,
					self.model.valid_to >= today,
					self.model.valid_to <= expiring_threshold
				)
			)
			expiring_result = await self.session.execute(expiring_query)
			expiring = expiring_result.scalar() or 0

			# 按类型统计
			type_query = select(
				self.model.license_type,
				func.count().label("count")
			).group_by(
				self.model.license_type
			)
			type_result = await self.session.execute(type_query)
			by_type = {
				row.license_type: row.count
				for row in type_result.fetchall()
			}

			return {
				"total": total,
				"active": active,
				"inactive": total - active,
				"expired": expired,
				"expiring": expiring,
				"valid": active - expired,
				"by_type": by_type
			}
		except Exception as e:
			raise RepositoryError(f"获取许可证统计失败: {str(e)}")

	async def extend_license (
			self,
			license_key: str,
			extension_days: int,
			new_valid_to: Optional[date] = None
	) -> Optional[LicenseKey]:
		"""
		延长许可证有效期

		Args:
			license_key: 许可证密钥
			extension_days: 延长的天数
			new_valid_to: 新的有效期结束日期（如果指定则忽略extension_days）

		Returns:
			更新后的许可证记录
		"""
		try:
			license_record = await self.get_by_license_key(license_key)
			if not license_record:
				raise NotFoundError(f"许可证不存在: {license_key}")

			if new_valid_to:
				valid_to = new_valid_to
			else:
				# 使用当前有效期或今天
				base_date = license_record.valid_to or date.today()
				valid_to = base_date + timedelta(days=extension_days)

			return await self.update(license_record.id, {
				"valid_to": valid_to,
				"updated_at": datetime.now()
			})
		except Exception as e:
			if isinstance(e, NotFoundError):
				raise e
			raise RepositoryError(f"延长许可证有效期失败: {str(e)}")

	async def transfer_license (
			self,
			license_key: str,
			new_user_id: int
	) -> Optional[LicenseKey]:
		"""
		转移许可证到新用户

		Args:
			license_key: 许可证密钥
			new_user_id: 新用户ID

		Returns:
			更新后的许可证记录
		"""
		try:
			license_record = await self.get_by_license_key(license_key)
			if not license_record:
				raise NotFoundError(f"许可证不存在: {license_key}")

			return await self.update(license_record.id, {
				"user_id": new_user_id,
				"updated_at": datetime.now()
			})
		except Exception as e:
			if isinstance(e, NotFoundError):
				raise e
			raise RepositoryError(f"转移许可证失败: {str(e)}")