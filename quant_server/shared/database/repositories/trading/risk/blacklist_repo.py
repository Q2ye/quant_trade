# -*- coding: utf-8 -*-
"""
黑名单数据仓库
提供黑名单管理的统一访问接口
位置：shared/database/repositories/trading/risk/blacklist_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.business_models import Blacklist


class BlacklistRepository(BaseRepository):
	"""黑名单数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, Blacklist)

	async def is_blacklisted (
			self,
			target_type: str,
			target_id: str,
			user_id: Optional[int] = None
	) -> bool:
		"""
		检查目标是否在黑名单中

		Args:
			target_type: 目标类型（stock/user/account）
			target_id: 目标标识
			user_id: 用户ID（用于用户特定黑名单检查）

		Returns:
			bool: 是否在黑名单中
		"""
		# 检查全局黑名单
		global_conditions = [
			Blacklist.target_type == target_type,
			Blacklist.target_id == target_id,
			Blacklist.list_type == 'global',
			Blacklist.is_active == True,
			or_(
				Blacklist.expire_date.is_(None),
				Blacklist.expire_date > datetime.now()
			)
		]

		global_exists = await self.count(*global_conditions) > 0

		if global_exists:
			return True

		# 检查用户特定黑名单
		if user_id:
			user_conditions = [
				Blacklist.target_type == target_type,
				Blacklist.target_id == target_id,
				Blacklist.list_type == 'user_specific',
				Blacklist.added_by == user_id,  # user_specific黑名单由用户自己维护
				Blacklist.is_active == True,
				or_(
					Blacklist.expire_date.is_(None),
					Blacklist.expire_date > datetime.now()
				)
			]

			user_exists = await self.count(*user_conditions) > 0

			if user_exists:
				return True

		return False

	async def is_stock_blacklisted (
			self,
			ts_code: str,
			user_id: Optional[int] = None
	) -> bool:
		"""
		检查股票是否在黑名单中

		Args:
			ts_code: 股票代码
			user_id: 用户ID（用于用户特定黑名单检查）

		Returns:
			bool: 是否在黑名单中
		"""
		return await self.is_blacklisted('stock', ts_code, user_id)

	async def is_user_blacklisted (
			self,
			user_id: int
	) -> bool:
		"""
		检查用户是否在黑名单中

		Args:
			user_id: 用户ID

		Returns:
			bool: 是否在黑名单中
		"""
		return await self.is_blacklisted('user', str(user_id), None)

	async def is_account_blacklisted (
			self,
			account_id: int,
			user_id: Optional[int] = None
	) -> bool:
		"""
		检查账户是否在黑名单中

		Args:
			account_id: 账户ID
			user_id: 用户ID（用于用户特定黑名单检查）

		Returns:
			bool: 是否在黑名单中
		"""
		return await self.is_blacklisted('account', str(account_id), user_id)

	async def add_to_blacklist (
			self,
			target_type: str,
			target_id: str,
			target_name: str,
			list_type: str,
			reason: str,
			added_by: int,
			expire_date: Optional[datetime] = None,
			metadata: Optional[Dict[str, Any]] = None
	) -> Optional[Blacklist]:
		"""
		添加到黑名单

		Args:
			target_type: 目标类型
			target_id: 目标标识
			target_name: 目标名称
			list_type: 名单类型（global/user_specific/system）
			reason: 加入原因
			added_by: 添加人ID
			expire_date: 过期时间
			metadata: 元数据

		Returns:
			Blacklist: 创建的黑名单记录，如果已存在则返回None
		"""
		# 检查是否已存在
		existing = await self.get_one(
			and_(
				Blacklist.target_type == target_type,
				Blacklist.target_id == target_id,
				Blacklist.list_type == list_type,
				Blacklist.is_active == True
			)
		)

		if existing:
			# 如果已存在，更新过期时间和原因
			update_data = {
				'reason': reason,
				'expire_date': expire_date,
				'is_active': True,
				'updated_at': datetime.now()
			}

			if metadata:
				update_data['metadata'] = metadata

			return await self.update(existing.id, update_data)

		# 创建新的黑名单记录
		blacklist_data = {
			'target_type': target_type,
			'target_id': target_id,
			'target_name': target_name,
			'list_type': list_type,
			'reason': reason,
			'added_by': added_by,
			'expire_date': expire_date,
			'is_active': True,
			'metadata': metadata or {}
		}

		return await self.create(blacklist_data)

	async def add_stock_to_blacklist (
			self,
			ts_code: str,
			stock_name: str,
			reason: str,
			added_by: int,
			list_type: str = 'global',
			expire_date: Optional[datetime] = None
	) -> Optional[Blacklist]:
		"""
		添加股票到黑名单

		Args:
			ts_code: 股票代码
			stock_name: 股票名称
			reason: 原因
			added_by: 添加人ID
			list_type: 名单类型
			expire_date: 过期日期

		Returns:
			Blacklist: 创建的黑名单记录
		"""
		return await self.add_to_blacklist(
			target_type='stock',
			target_id=ts_code,
			target_name=stock_name,
			list_type=list_type,
			reason=reason,
			added_by=added_by,
			expire_date=expire_date,
			metadata={'stock_code': ts_code, 'stock_name': stock_name}
		)

	async def add_user_to_blacklist (
			self,
			user_id: int,
			username: str,
			reason: str,
			added_by: int,
			expire_date: Optional[datetime] = None
	) -> Optional[Blacklist]:
		"""
		添加用户到黑名单

		Args:
			user_id: 用户ID
			username: 用户名
			reason: 原因
			added_by: 添加人ID
			expire_date: 过期日期

		Returns:
			Blacklist: 创建的黑名单记录
		"""
		return await self.add_to_blacklist(
			target_type='user',
			target_id=str(user_id),
			target_name=username,
			list_type='global',
			reason=reason,
			added_by=added_by,
			expire_date=expire_date,
			metadata={'user_id': user_id, 'username': username}
		)

	async def remove_from_blacklist (
			self,
			target_type: str,
			target_id: str,
			list_type: str = 'global'
	) -> bool:
		"""
		从黑名单中移除

		Args:
			target_type: 目标类型
			target_id: 目标标识
			list_type: 名单类型

		Returns:
			bool: 是否成功移除
		"""
		blacklist = await self.get_one(
			and_(
				Blacklist.target_type == target_type,
				Blacklist.target_id == target_id,
				Blacklist.list_type == list_type,
				Blacklist.is_active == True
			)
		)

		if not blacklist:
			return False

		# 软删除
		return await self.delete(blacklist.id, soft=True)

	async def remove_stock_from_blacklist (
			self,
			ts_code: str,
			list_type: str = 'global'
	) -> bool:
		"""
		从黑名单中移除股票

		Args:
			ts_code: 股票代码
			list_type: 名单类型

		Returns:
			bool: 是否成功移除
		"""
		return await self.remove_from_blacklist('stock', ts_code, list_type)

	async def remove_user_from_blacklist (
			self,
			user_id: int
	) -> bool:
		"""
		从黑名单中移除用户

		Args:
			user_id: 用户ID

		Returns:
			bool: 是否成功移除
		"""
		return await self.remove_from_blacklist('user', str(user_id), 'global')

	async def get_blacklisted_stocks (
			self,
			list_type: Optional[str] = None,
			include_expired: bool = False
	) -> List[Blacklist]:
		"""
		获取黑名单股票列表

		Args:
			list_type: 名单类型筛选
			include_expired: 是否包含已过期的记录

		Returns:
			List[Blacklist]: 黑名单股票列表
		"""
		conditions = [
			Blacklist.target_type == 'stock',
			Blacklist.is_active == True
		]

		if list_type:
			conditions.append(Blacklist.list_type == list_type)

		if not include_expired:
			conditions.append(
				or_(
					Blacklist.expire_date.is_(None),
					Blacklist.expire_date > datetime.now()
				)
			)

		return await self.get_many(
			*conditions,
			order_by=Blacklist.created_at.desc()
		)

	async def get_blacklisted_users (
			self,
			include_expired: bool = False
	) -> List[Blacklist]:
		"""
		获取黑名单用户列表

		Args:
			include_expired: 是否包含已过期的记录

		Returns:
			List[Blacklist]: 黑名单用户列表
		"""
		conditions = [
			Blacklist.target_type == 'user',
			Blacklist.is_active == True
		]

		if not include_expired:
			conditions.append(
				or_(
					Blacklist.expire_date.is_(None),
					Blacklist.expire_date > datetime.now()
				)
			)

		return await self.get_many(
			*conditions,
			order_by=Blacklist.created_at.desc()
		)

	async def get_user_specific_blacklist (
			self,
			user_id: int,
			target_type: Optional[str] = None
	) -> List[Blacklist]:
		"""
		获取用户特定的黑名单

		Args:
			user_id: 用户ID
			target_type: 目标类型筛选

		Returns:
			List[Blacklist]: 用户特定黑名单列表
		"""
		conditions = [
			Blacklist.added_by == user_id,
			Blacklist.list_type == 'user_specific',
			Blacklist.is_active == True,
			or_(
				Blacklist.expire_date.is_(None),
				Blacklist.expire_date > datetime.now()
			)
		]

		if target_type:
			conditions.append(Blacklist.target_type == target_type)

		return await self.get_many(
			*conditions,
			order_by=Blacklist.created_at.desc()
		)

	async def cleanup_expired_entries (self) -> int:
		"""
		清理过期的黑名单记录

		Returns:
			int: 清理的记录数
		"""
		# 查找过期的记录
		expired_entries = await self.get_many(
			and_(
				Blacklist.expire_date.is_not(None),
				Blacklist.expire_date <= datetime.now(),
				Blacklist.is_active == True
			)
		)

		# 批量禁用过期的记录
		cleaned = 0
		for entry in expired_entries:
			success = await self.delete(entry.id, soft=True)
			if success:
				cleaned += 1

		return cleaned

	async def get_blacklist_statistics (self) -> Dict[str, Any]:
		"""
		获取黑名单统计信息

		Returns:
			Dict[str, Any]: 统计信息
		"""
		# 按目标类型统计
		type_stats_query = select(
			Blacklist.target_type,
			func.count(Blacklist.id).label('count')
		).where(
			Blacklist.is_active == True
		).group_by(
			Blacklist.target_type
		)

		type_stats_result = await self.session.execute(type_stats_query)
		type_stats = [
			{'target_type': row[0], 'count': row[1]}
			for row in type_stats_result.all()
		]

		# 按名单类型统计
		list_type_stats_query = select(
			Blacklist.list_type,
			func.count(Blacklist.id).label('count')
		).where(
			Blacklist.is_active == True
		).group_by(
			Blacklist.list_type
		)

		list_type_stats_result = await self.session.execute(list_type_stats_query)
		list_type_stats = [
			{'list_type': row[0], 'count': row[1]}
			for row in list_type_stats_result.all()
		]

		# 统计即将过期的记录
		soon_expire_query = select(
			func.count(Blacklist.id)
		).where(
			and_(
				Blacklist.is_active == True,
				Blacklist.expire_date.is_not(None),
				Blacklist.expire_date <= datetime.now() + timedelta(days=7),
				Blacklist.expire_date > datetime.now()
			)
		)

		soon_expire_result = await self.session.execute(soon_expire_query)
		soon_expire_count = soon_expire_result.scalar() or 0

		return {
			'total_active': sum(stat['count'] for stat in type_stats),
			'by_target_type': type_stats,
			'by_list_type': list_type_stats,
			'soon_expire_count': soon_expire_count,
			'updated_at': datetime.now()
		}