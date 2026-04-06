# -*- coding: utf-8 -*-
"""
权限数据仓库
提供用户权限数据的统一访问接口
位置：shared/database/repositories/permission_repo.py
"""

from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import SysPermission
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError


class PermissionRepository:
	"""权限数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, SysPermission)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> SysPermission:
		"""创建权限记录"""
		return await self.base_repo.create(data)

	async def get (self, id: Any) -> Optional[SysPermission]:
		"""根据ID获取权限记录"""
		return await self.base_repo.get(id)

	async def update (self, id: Any, data: Dict[str, Any]) -> Optional[SysPermission]:
		"""更新权限记录"""
		return await self.base_repo.update(id, data)

	async def delete (self, id: Any, soft: bool = True) -> bool:
		"""删除权限记录"""
		return await self.base_repo.delete(id, soft)

	async def get_one (self, *filters) -> Optional[SysPermission]:
		"""根据条件获取单个权限记录"""
		try:
			query = select(SysPermission)
			for filter_condition in filters:
				query = query.where(filter_condition)
			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取单个权限记录失败: {str(e)}")

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by = None
	) -> List[SysPermission]:
		"""根据条件获取多个权限记录"""
		try:
			query = select(SysPermission)
			for filter_condition in filters:
				query = query.where(filter_condition)
			if order_by:
				query = query.order_by(order_by)
			query = query.offset(skip).limit(limit)
			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取多个权限记录失败: {str(e)}")

	async def count (self, *filters) -> int:
		"""统计权限记录数"""
		try:
			query = select(func.count()).select_from(SysPermission)
			for filter_condition in filters:
				query = query.where(filter_condition)
			result = await self.session.execute(query)
			return result.scalar() or 0
		except Exception as e:
			raise RepositoryError(f"统计权限记录数失败: {str(e)}")

	# ==================== 业务查询方法 ====================

	async def get_user_permissions (self, user_id: str) -> List[SysPermission]:
		"""获取用户的所有权限"""
		return await self.get_many(
			SysPermission.user_id == user_id,
			order_by=SysPermission.module.asc()
		)

	async def get_user_module_permission (
			self,
			user_id: str,
			module: str
	) -> Optional[SysPermission]:
		"""获取用户在特定模块的权限"""
		return await self.get_one(
			and_(
				SysPermission.user_id == user_id,
				SysPermission.module == module
			)
		)

	async def has_permission (
			self,
			user_id: str,
			module: str,
			permission_type: str
	) -> bool:
		"""检查用户是否拥有特定权限

		Args:
			user_id: 用户ID
			module: 模块名称
			permission_type: 权限类型 ('read', 'write', 'execute')

		Returns:
			bool: 是否拥有权限
		"""
		permission = await self.get_user_module_permission(user_id, module)

		if not permission:
			return False

		if permission_type == 'read':
			return permission.can_read
		elif permission_type == 'write':
			return permission.can_write
		elif permission_type == 'execute':
			return permission.can_execute
		else:
			return False

	async def get_users_with_permission (
			self,
			module: str,
			permission_type: str
	) -> List[int]:
		"""获取拥有特定权限的用户ID列表"""
		query = select(SysPermission.user_id)

		if permission_type == 'read':
			query = query.where(
				and_(
					SysPermission.module == module,
					SysPermission.can_read == True
				)
			)
		elif permission_type == 'write':
			query = query.where(
				and_(
					SysPermission.module == module,
					SysPermission.can_write == True
				)
			)
		elif permission_type == 'execute':
			query = query.where(
				and_(
					SysPermission.module == module,
					SysPermission.can_execute == True
				)
			)
		else:
			# 如果没有指定权限类型，返回所有拥有该模块任何权限的用户
			query = query.where(
				and_(
					SysPermission.module == module,
					or_(
						SysPermission.can_read == True,
						SysPermission.can_write == True,
						SysPermission.can_execute == True
					)
				)
			)

		result = await self.session.execute(query)
		return [row[0] for row in result.all()]

	async def set_permission (
			self,
			user_id: str,
			module: str,
			can_read: bool = None,
			can_write: bool = None,
			can_execute: bool = None
	) -> Optional[SysPermission]:
		"""设置用户权限"""
		# 检查是否已存在权限记录
		existing = await self.get_user_module_permission(user_id, module)

		if existing:
			# 更新现有权限
			update_data = {}
			if can_read is not None:
				update_data['can_read'] = can_read
			if can_write is not None:
				update_data['can_write'] = can_write
			if can_execute is not None:
				update_data['can_execute'] = can_execute

			if update_data:
				return await self.update(existing.id, update_data)
			return existing
		else:
			# 创建新权限记录
			permission_data = {
				'user_id': user_id,
				'module': module,
				'can_read': can_read if can_read is not None else False,
				'can_write': can_write if can_write is not None else False,
				'can_execute': can_execute if can_execute is not None else False
			}
			return await self.create(permission_data)

	async def grant_permission (
			self,
			user_id: str,
			module: str,
			permission_type: str
	) -> bool:
		"""授予权限"""
		permission = await self.get_user_module_permission(user_id, module)

		if permission:
			# 更新现有权限
			update_data = {}
			if permission_type == 'read':
				update_data['can_read'] = True
			elif permission_type == 'write':
				update_data['can_write'] = True
			elif permission_type == 'execute':
				update_data['can_execute'] = True

			if update_data:
				result = await self.update(permission.id, update_data)
				return result is not None
			return False
		else:
			# 创建新权限记录
			permission_data = {
				'user_id': user_id,
				'module': module,
				'can_read': permission_type == 'read',
				'can_write': permission_type == 'write',
				'can_execute': permission_type == 'execute'
			}
			result = await self.create(permission_data)
			return result is not None

	async def revoke_permission (
			self,
			user_id: str,
			module: str,
			permission_type: str
	) -> bool:
		"""撤销权限"""
		permission = await self.get_user_module_permission(user_id, module)

		if not permission:
			return False

		update_data = {}
		if permission_type == 'read':
			update_data['can_read'] = False
		elif permission_type == 'write':
			update_data['can_write'] = False
		elif permission_type == 'execute':
			update_data['can_execute'] = False

		if update_data:
			result = await self.update(permission.id, update_data)
			return result is not None

		return False

	async def revoke_all_permissions (self, user_id: str) -> int:
		"""撤销用户的所有权限"""
		# 获取用户的所有权限
		permissions = await self.get_user_permissions(user_id)

		# 删除所有权限记录
		count = 0
		for permission in permissions:
			success = await self.delete(permission.id, soft=False)
			if success:
				count += 1

		return count

	async def copy_permissions (
			self,
			from_user_id: str,
			to_user_id: str
	) -> Dict[str, int]:
		"""复制权限（从一个用户复制到另一个用户）"""
		# 获取源用户的所有权限
		source_permissions = await self.get_user_permissions(from_user_id)

		if not source_permissions:
			return {'copied': 0, 'skipped': 0, 'total': 0}

		# 复制权限
		copied = 0
		skipped = 0

		for source_perm in source_permissions:
			# 检查目标用户是否已有该模块权限
			existing = await self.get_user_module_permission(to_user_id, source_perm.module)

			if existing:
				# 跳过已存在的权限
				skipped += 1
				continue

			# 创建新权限记录
			permission_data = {
				'user_id': to_user_id,
				'module': source_perm.module,
				'can_read': source_perm.can_read,
				'can_write': source_perm.can_write,
				'can_execute': source_perm.can_execute
			}

			result = await self.create(permission_data)
			if result:
				copied += 1
			else:
				skipped += 1

		return {
			'copied': copied,
			'skipped': skipped,
			'total': len(source_permissions)
		}

	async def get_permission_summary (self) -> Dict[str, Any]:
		"""获取权限数据摘要"""
		# 统计总权限记录数
		total_count = await self.count()

		# 统计按模块分组的权限数
		module_query = select(
			SysPermission.module,
			func.count(SysPermission.id).label('count')
		).group_by(
			SysPermission.module
		)

		module_result = await self.session.execute(module_query)
		module_stats = {row[0]: row[1] for row in module_result.all()}

		# 统计权限类型分布
		read_count = await self.count(SysPermission.can_read == True)
		write_count = await self.count(SysPermission.can_write == True)
		execute_count = await self.count(SysPermission.can_execute == True)

		# 统计用户权限分布
		user_query = select(
			SysPermission.user_id,
			func.count(SysPermission.id).label('permission_count')
		).group_by(
			SysPermission.user_id
		).order_by(
			func.count(SysPermission.id).desc()
		)

		user_result = await self.session.execute(user_query)
		user_stats = [{'user_id': row[0], 'permission_count': row[1]} for row in user_result.all()]

		return {
			'total_permissions': total_count,
			'module_stats': module_stats,
			'permission_type_stats': {
				'read': read_count,
				'write': write_count,
				'execute': execute_count
			},
			'user_stats': user_stats[:10],  # 只返回前10个
			'unique_users': len(user_stats),
			'unique_modules': len(module_stats)
		}

	async def get_modules (self) -> List[str]:
		"""获取所有模块列表（去重）"""
		query = select(SysPermission.module).distinct().order_by(SysPermission.module.asc())

		result = await self.session.execute(query)
		return [row[0] for row in result.all()]

	async def batch_set_permissions (
			self,
			permissions_data: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""批量设置权限"""
		success_count = 0
		failed_count = 0

		for perm_data in permissions_data:
			user_id = perm_data.get('user_id')
			module = perm_data.get('module')

			if not user_id or not module:
				failed_count += 1
				continue

			try:
				can_read = perm_data.get('can_read')
				can_write = perm_data.get('can_write')
				can_execute = perm_data.get('can_execute')

				result = await self.set_permission(
					user_id, module, can_read, can_write, can_execute
				)

				if result:
					success_count += 1
				else:
					failed_count += 1
			except Exception as e:
				print(f"设置权限失败: {str(e)}")
				failed_count += 1

		return {
			'success': success_count,
			'failed': failed_count,
			'total': len(permissions_data)
		}

	async def export_permissions (self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
		"""导出权限数据"""
		if user_id:
			permissions = await self.get_user_permissions(user_id)
		else:
			permissions = await self.get_many(limit=1000)  # 限制导出数量

		return [
			{
				'id': p.id,
				'user_id': p.user_id,
				'module': p.module,
				'can_read': p.can_read,
				'can_write': p.can_write,
				'can_execute': p.can_execute,
				'created_at': p.created_at.isoformat() if p.created_at else None,
				'updated_at': p.updated_at.isoformat() if p.updated_at else None
			}
			for p in permissions
		]