# -*- coding: utf-8 -*-
"""
角色数据仓库
提供系统角色数据的统一访问接口
位置：shared/database/repositories/role_repo.py

注意：根据现有模型，角色功能可能集成在SysUser表中（role字段）
如果需要有独立的角色表，需要先创建Role模型
这里假设存在一个SysRole模型
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BusinessException
# 假设存在SysRole模型
from shared.database.models.business_models import SysRole, SysUser
from shared.database.repositories.base import BaseRepository


class RoleRepository:
	"""角色数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, SysRole)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> SysRole:
		"""创建角色记录"""
		return await self.base_repo.create(data)

	async def get (self, id: str) -> Optional[SysRole]:
		"""根据ID获取角色记录"""
		return await self.base_repo.get(id)

	async def update (self, id: str, data: Dict[str, Any]) -> Optional[SysRole]:
		"""更新角色记录"""
		return await self.base_repo.update(id, data)

	async def delete (self, id: str, soft: bool = True) -> bool:
		"""删除角色记录"""
		return await self.base_repo.delete(id, soft)

	async def get_one (self, **filters) -> Optional[SysRole]:
		"""根据条件获取单个角色记录"""
		# 由于 BaseRepository 没有 get_one 方法，使用 get_many 并限制为 1
		roles = await self.base_repo.get_many(limit=1, **filters)
		return roles[0] if roles else None

	async def get_many (
			self,
			skip: int = 0,
			limit: int = 100,
			**filters
	) -> List[SysRole]:
		"""根据条件获取多个角色记录"""
		return await self.base_repo.get_many(skip=skip, limit=limit, **filters)

	async def count (self, **filters) -> int:
		"""统计角色记录数"""
		return await self.base_repo.count(**filters)

	# ==================== 业务查询方法 ====================

	async def get_by_name (self, name: str) -> Optional[SysRole]:
		"""根据角色名称获取角色"""
		return await self.base_repo.get_by(name=name)

	async def get_by_code (self, code: str) -> Optional[SysRole]:
		"""根据角色代码获取角色"""
		return await self.base_repo.get_by(code=code)

	async def get_all_roles (self, include_inactive: bool = False) -> List[SysRole]:
		"""获取所有角色"""
		filters = {}
		if not include_inactive:
			filters['is_active'] = True

		return await self.get_many(
			**filters
		)

	async def get_roles_by_type (self, role_type: str) -> List[SysRole]:
		"""根据角色类型获取角色

		注意：SysRole 模型当前不含 role_type 列。此方法暂时返回所有活跃角色。
		待数据库 migration 添加 role_type 列后，将恢复精确过滤。
		"""
		import logging
		logging.getLogger(__name__).warning(
			"get_roles_by_type: SysRole 模型不含 role_type 列，返回所有活跃角色"
		)
		return await self.get_many(is_active=True)

	async def get_roles_with_permissions (self) -> List[Dict[str, Any]]:
		"""获取角色及其权限信息（需要关联权限表）"""
		# 这里假设角色和权限有关联关系
		# 实际实现需要根据数据库设计调整

		# 使用 get_many 方法获取活跃角色
		roles = await self.get_many(is_active=True)

		# 这里只是示例，实际需要查询关联的权限
		role_list = []
		for role in roles:
			role_data = {
				'id': getattr(role, 'id', None),
				'name': getattr(role, 'name', None),
				'code': getattr(role, 'code', None),
				'description': getattr(role, 'description', None),
				'permissions': []  # 实际需要从关联表查询
			}
			role_list.append(role_data)

		return role_list

	async def search_roles (
			self,
			role_type: Optional[str] = None,
			is_active: Optional[bool] = True,
			limit: int = 100
	) -> List[SysRole]:
		"""搜索角色

		注意：SysRole 模型当前不含 role_type 列，role_type 参数被忽略。
		"""
		filters = {}

		if is_active is not None:
			filters['is_active'] = is_active

		return await self.get_many(
			limit=limit,
			**filters
		)

	async def get_role_hierarchy (self) -> Dict[str, Any]:
		"""获取角色层级结构

		注意：SysRole 模型当前不含 parent_id 列（层级关系）。
		此方法降级为返回扁平角色列表。待 migration 添加 parent_id 后启用层级查询。
		"""
		import logging
		logging.getLogger(__name__).warning(
			"get_role_hierarchy: SysRole 模型不含 parent_id 列，返回扁平角色列表"
		)
		# 降级：返回所有活跃角色（扁平列表）
		all_roles = await self.get_many(is_active=True)
		flat_list = []
		for role in all_roles:
			flat_list.append({
				'id': getattr(role, 'id', None),
				'name': getattr(role, 'name', None),
				'code': getattr(role, 'code', None),
				'description': getattr(role, 'description', None),
				'children': [],  # 扁平列表，无子节点
			})
		return {'hierarchy': flat_list}

	async def _get_role_children (self, parent_id: str) -> List[Dict[str, Any]]:
		"""获取子角色（预留扩展）

		注意：SysRole 模型当前不含 parent_id 列。此方法返回空列表。
		待 migration 添加 parent_id 后启用。
		"""
		return []

		children_data = []
		for child in children:
			child_data = {
				'id': getattr(child, 'id', None),
				'name': getattr(child, 'name', None),
				'code': getattr(child, 'code', None),
				'children': await self._get_role_children(getattr(child, 'id', None))
			}
			children_data.append(child_data)

		return children_data

	async def get_role_statistics (self) -> Dict[str, Any]:
		"""获取角色统计信息"""
		# 总角色数
		total_count = await self.count()

		# 活跃角色数
		active_count = await self.count(is_active=True)

		# 按 is_default 分组统计（默认角色 vs 自定义角色）
		type_query = select(
			SysRole.is_default, func.count(SysRole.id)
		).group_by(SysRole.is_default)
		type_result = await self.session.execute(type_query)
		type_stats_dict = {}
		for is_default_val, count in type_result.all():
			label = 'default' if is_default_val else 'custom'
			type_stats_dict[label] = count

		# 按创建时间统计（最近30天）
		cutoff_date = datetime.now() - timedelta(days=30)
		recent_query = select(func.count(SysRole.id)).where(
			SysRole.created_at >= cutoff_date
		)
		recent_result = await self.session.execute(recent_query)
		recent_count = recent_result.scalar() or 0

		return {
			'total_count': total_count,
			'active_count': active_count,
			'inactive_count': total_count - active_count,
			'type_stats': type_stats_dict,
			'recent_30_days_count': recent_count
		}

	async def assign_permission_to_role (
			self,
			role_id: str,
			permission_id: str
	) -> bool:
		"""
		为角色分配权限
		
		Args:
			role_id: 角色ID
			permission_id: 权限ID
			
		Returns:
			是否成功分配权限
		"""
		try:
			# 检查角色是否存在
			role = await self.base_repo.get(role_id)
			if not role:
				return False

			# 使用角色的permissions字段
			if hasattr(role, 'permissions'):
				if isinstance(role.permissions, list):
					if permission_id not in role.permissions:
						role.permissions.append(permission_id)
						await self.session.commit()
					return True
				else:
					# 如果permissions字段不是列表，更新为列表
					role.permissions = [permission_id]
					await self.session.commit()
					return True
			else:
				# 如果角色没有permissions字段，返回False
				return False

		except BusinessException:
			await self.session.rollback()
			return False

	async def remove_permission_from_role (
			self,
			role_id: str,
			permission_id: str
	) -> bool:
		"""
		从角色移除权限
		
		Args:
			role_id: 角色ID
			permission_id: 权限ID
			
		Returns:
			是否成功移除权限
		"""
		try:
			# 检查角色是否存在
			role = await self.base_repo.get(role_id)
			if not role:
				return False

			# 使用角色的permissions字段
			if hasattr(role, 'permissions'):
				if isinstance(role.permissions, list):
					if permission_id in role.permissions:
						role.permissions.remove(permission_id)
						await self.session.commit()
						return True
					else:
						# 权限不存在于列表中
						return False
				else:
					# 如果permissions字段不是列表，无法移除
					return False
			else:
				# 如果角色没有permissions字段，返回False
				return False

		except BusinessException:
			await self.session.rollback()
			return False

	async def get_role_permissions (self, role_id: str) -> List[Dict[str, Any]]:
		"""
		获取角色的所有权限
		
		Args:
			role_id: 角色ID
			
		Returns:
			权限信息列表
		"""
		try:
			# 检查角色是否存在
			role = await self.base_repo.get(role_id)
			if not role:
				return []

			# 使用角色的permissions字段
			if hasattr(role, 'permissions'):
				if isinstance(role.permissions, list):
					# 返回权限ID列表
					return [{'id': perm_id, 'name': f'Permission_{perm_id}'} for perm_id in role.permissions]
				else:
					# 如果permissions字段不是列表，返回空列表
					return []
			else:
				# 如果角色没有permissions字段，返回空列表
				return []

		except BusinessException:
			# 记录错误日志
			return []

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[SysRole]:
		"""批量创建角色记录"""
		return await self.base_repo.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: Optional[List[str]] = None
	) -> List[SysRole]:
		"""批量插入或更新角色记录"""
		if match_fields is None:
			match_fields = ['code']
		return await self.base_repo.batch_upsert(match_fields, data_list)

	async def deactivate_role (self, role_id: str) -> bool:
		"""停用角色"""
		role = await self.base_repo.get(role_id)
		if not role:
			return False

		result = await self.base_repo.update(role_id, {'is_active': False})
		return result is not None

	async def activate_role (self, role_id: str) -> bool:
		"""激活角色"""
		role = await self.base_repo.get(role_id)
		if not role:
			return False

		result = await self.base_repo.update(role_id, {'is_active': True})
		return result is not None

	async def get_users_by_role (self, role_id: str) -> List[str]:
		"""
		获取拥有该角色的用户ID列表
		
		Args:
			role_id: 角色ID
			
		Returns:
			用户ID列表
		"""
		try:
			# 检查角色是否存在
			role = await self.base_repo.get(role_id)
			if not role:
				return []

			# 尝试使用用户表的role字段
			try:

				query = select(SysUser.id).where(
					SysUser.role == role_id
				)

				result = await self.session.execute(query)
				user_ids = [row[0] for row in result.all()]

				return user_ids

			except ImportError:
				# 如果SysUser模型不存在，返回空列表
				return []

		except BusinessException:
			# 记录错误日志
			return []

	async def get_role_usage_statistics (self) -> Dict[str, Any]:
		"""
		获取角色使用情况统计
		
		Returns:
			角色使用统计信息
		"""
		try:
			# 尝试使用用户表的role字段统计
			try:
				from shared.database.models.business_models import SysUser

				# 获取所有角色
				roles = await self.get_all_roles(include_inactive=False)

				statistics = []
				for role in roles:
					# 统计拥有该角色的用户数
					user_count_query = select(func.count(SysUser.id)).where(
						SysUser.role == getattr(role, 'role_code', None)
					)
					user_count_result = await self.session.execute(user_count_query)
					user_count = user_count_result.scalar() or 0

					statistics.append({
						'role_id': getattr(role, 'id', None),
						'role_name': getattr(role, 'role_name', None),
						'role_code': getattr(role, 'role_code', None),
						'role_type': getattr(role, 'role_type', None),
						'user_count': user_count
					})

				# 按用户数排序
				statistics.sort(key=lambda x: x['user_count'], reverse=True)

				# 计算总体统计
				total_roles = len(statistics)
				total_users = sum(stat['user_count'] for stat in statistics)
				avg_users_per_role = total_users / total_roles if total_roles > 0 else 0

				# 按角色类型统计
				role_type_stats = {}
				for stat in statistics:
					role_type = stat['role_type'] or 'unknown'
					if role_type not in role_type_stats:
						role_type_stats[role_type] = {
							'count': 0,
							'user_count': 0
						}
					role_type_stats[role_type]['count'] += 1
					role_type_stats[role_type]['user_count'] += stat['user_count']

				return {
					'statistics': statistics,
					'summary': {
						'total_roles': total_roles,
						'total_users': total_users,
						'avg_users_per_role': round(avg_users_per_role, 2),
						'max_users_per_role': max((stat['user_count'] for stat in statistics), default=0),
						'min_users_per_role': min((stat['user_count'] for stat in statistics), default=0)
					},
					'role_type_stats': role_type_stats
				}

			except ImportError:
				# 如果SysUser模型不存在，返回基础统计
				roles = await self.get_all_roles(include_inactive=False)

				statistics = [{
					'role_id': getattr(role, 'id', None),
					'role_name': getattr(role, 'role_name', None),
					'role_code': getattr(role, 'role_code', None),
					'role_type': getattr(role, 'role_type', None),
					'user_count': 0  # 无法统计用户数
				} for role in roles]

				return {
					'statistics': statistics,
					'summary': {
						'total_roles': len(statistics),
						'total_users': 0,
						'avg_users_per_role': 0,
						'max_users_per_role': 0,
						'min_users_per_role': 0
					},
					'role_type_stats': {}
				}

		except BusinessException:
			# 记录错误日志
			return {
				'statistics': [],
				'summary': {
					'total_roles': 0,
					'total_users': 0,
					'avg_users_per_role': 0,
					'max_users_per_role': 0,
					'min_users_per_role': 0
				},
				'role_type_stats': {}
			}