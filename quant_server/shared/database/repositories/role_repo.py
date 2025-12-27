# -*- coding: utf-8 -*-
"""
角色数据仓库
提供系统角色数据的统一访问接口
位置：shared/database/repositories/role_repo.py

注意：根据现有模型，角色功能可能集成在SysUser表中（role字段）
如果需要有独立的角色表，需要先创建Role模型
这里假设存在一个SysRole模型
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, distinct

# 假设存在SysRole模型
from quant_server.shared.database.models.business_models import SysRole
from .base import BaseRepository


class RoleRepository:
	"""角色数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, SysRole)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> SysRole:
		"""创建角色记录"""
		return await self.base_repo.create(data)

	async def get (self, id: int) -> Optional[SysRole]:
		"""根据ID获取角色记录"""
		return await self.base_repo.get(id)

	async def update (self, id: int, data: Dict[str, Any]) -> Optional[SysRole]:
		"""更新角色记录"""
		return await self.base_repo.update(id, data)

	async def delete (self, id: int, soft: bool = True) -> bool:
		"""删除角色记录"""
		return await self.base_repo.delete(id, soft)

	async def get_one (self, *filters) -> Optional[SysRole]:
		"""根据条件获取单个角色记录"""
		return await self.base_repo.get_one(*filters)

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by: str = None
	) -> List[SysRole]:
		"""根据条件获取多个角色记录"""
		return await self.base_repo.get_many(*filters, skip=skip, limit=limit, order_by=order_by)

	async def count (self, *filters) -> int:
		"""统计角色记录数"""
		return await self.base_repo.count(*filters)

	# ==================== 业务查询方法 ====================

	async def get_by_name (self, name: str) -> Optional[SysRole]:
		"""根据角色名称获取角色"""
		return await self.get_one(SysRole.name == name)

	async def get_by_code (self, code: str) -> Optional[SysRole]:
		"""根据角色代码获取角色"""
		return await self.get_one(SysRole.code == code)

	async def get_all_roles (self, include_inactive: bool = False) -> List[SysRole]:
		"""获取所有角色"""
		filters = []
		if not include_inactive:
			filters.append(SysRole.is_active == True)

		return await self.get_many(
			*filters,
			order_by=SysRole.name.asc()
		)

	async def get_roles_by_type (self, role_type: str) -> List[SysRole]:
		"""根据角色类型获取角色"""
		return await self.get_many(
			SysRole.role_type == role_type,
			order_by=SysRole.name.asc()
		)

	async def get_roles_with_permissions (self) -> List[Dict[str, Any]]:
		"""获取角色及其权限信息（需要关联权限表）"""
		# 这里假设角色和权限有关联关系
		# 实际实现需要根据数据库设计调整

		query = select(SysRole).where(
			SysRole.is_active == True
		).order_by(
			SysRole.name.asc()
		)

		result = await self.session.execute(query)
		roles = result.scalars().all()

		# 这里只是示例，实际需要查询关联的权限
		role_list = []
		for role in roles:
			role_data = {
				'id': role.id,
				'name': role.name,
				'code': role.code,
				'description': role.description,
				'permissions': []  # 实际需要从关联表查询
			}
			role_list.append(role_data)

		return role_list

	async def search_roles (
			self,
			keyword: Optional[str] = None,
			role_type: Optional[str] = None,
			is_active: Optional[bool] = True,
			limit: int = 100
	) -> List[SysRole]:
		"""搜索角色"""
		filters = []

		if keyword:
			filters.append(
				or_(
					SysRole.name.like(f"%{keyword}%"),
					SysRole.code.like(f"%{keyword}%"),
					SysRole.description.like(f"%{keyword}%")
				)
			)

		if role_type:
			filters.append(SysRole.role_type == role_type)

		if is_active is not None:
			filters.append(SysRole.is_active == is_active)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=SysRole.name.asc()
		)

	async def get_role_hierarchy (self) -> Dict[str, Any]:
		"""获取角色层级结构"""
		# 这里假设角色有parent_id字段表示层级关系
		# 实际实现需要根据数据库设计调整

		query = select(SysRole).where(
			and_(
				SysRole.is_active == True,
				SysRole.parent_id.is_(None)  # 顶级角色
			)
		).order_by(
			SysRole.name.asc()
		)

		result = await self.session.execute(query)
		top_roles = result.scalars().all()

		hierarchy = []
		for role in top_roles:
			role_data = {
				'id': role.id,
				'name': role.name,
				'code': role.code,
				'children': await self._get_role_children(role.id)
			}
			hierarchy.append(role_data)

		return {'hierarchy': hierarchy}

	async def _get_role_children (self, parent_id: int) -> List[Dict[str, Any]]:
		"""获取子角色（递归）"""
		query = select(SysRole).where(
			and_(
				SysRole.is_active == True,
				SysRole.parent_id == parent_id
			)
		).order_by(
			SysRole.name.asc()
		)

		result = await self.session.execute(query)
		children = result.scalars().all()

		children_data = []
		for child in children:
			child_data = {
				'id': child.id,
				'name': child.name,
				'code': child.code,
				'children': await self._get_role_children(child.id)
			}
			children_data.append(child_data)

		return children_data

	async def get_role_statistics (self) -> Dict[str, Any]:
		"""获取角色统计信息"""
		# 总角色数
		total_count = await self.count()

		# 活跃角色数
		active_count = await self.count(SysRole.is_active == True)

		# 按类型统计
		type_stats = await self.session.execute(
			select(
				SysRole.role_type,
				func.count(SysRole.id).label('count')
			).where(
				SysRole.is_active == True
			).group_by(
				SysRole.role_type
			).order_by(
				func.count(SysRole.id).desc()
			)
		)

		type_stats_dict = {row[0]: row[1] for row in type_stats.all() if row[0]}

		# 按创建时间统计（最近30天）
		thirty_days_ago = datetime.now() - timedelta(days=30)
		recent_count = await self.count(
			and_(
				SysRole.created_at >= thirty_days_ago,
				SysRole.is_active == True
			)
		)

		return {
			'total_count': total_count,
			'active_count': active_count,
			'inactive_count': total_count - active_count,
			'type_stats': type_stats_dict,
			'recent_30_days_count': recent_count
		}

	async def assign_permission_to_role (
			self,
			role_id: int,
			permission_id: int
	) -> bool:
		"""为角色分配权限（需要关联表操作）"""
		# 这里假设有RolePermission关联表
		# 实际实现需要根据数据库设计调整
		try:
			# 示例代码，实际需要插入到关联表
			# await self.session.execute(
			#     insert(RolePermission).values(
			#         role_id=role_id,
			#         permission_id=permission_id
			#     )
			# )
			# await self.session.commit()
			return True
		except Exception:
			return False

	async def remove_permission_from_role (
			self,
			role_id: int,
			permission_id: int
	) -> bool:
		"""从角色移除权限"""
		try:
			# 示例代码，实际需要从关联表删除
			# await self.session.execute(
			#     delete(RolePermission).where(
			#         and_(
			#             RolePermission.role_id == role_id,
			#             RolePermission.permission_id == permission_id
			#         )
			#     )
			# )
			# await self.session.commit()
			return True
		except Exception:
			return False

	async def get_role_permissions (self, role_id: int) -> List[Dict[str, Any]]:
		"""获取角色的所有权限"""
		# 这里假设有RolePermission关联表和Permission表
		# 实际实现需要根据数据库设计调整

		# 示例代码
		# query = select(Permission).join(
		#     RolePermission, RolePermission.permission_id == Permission.id
		# ).where(
		#     RolePermission.role_id == role_id
		# ).order_by(Permission.name.asc())

		# result = await self.session.execute(query)
		# permissions = result.scalars().all()

		# return [{'id': p.id, 'name': p.name, 'code': p.code} for p in permissions]

		return []  # 返回空列表，实际需要实现

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[SysRole]:
		"""批量创建角色记录"""
		return await self.base_repo.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['code']
	) -> List[SysRole]:
		"""批量插入或更新角色记录"""
		return await self.base_repo.batch_upsert(data_list, match_fields)

	async def deactivate_role (self, role_id: int) -> bool:
		"""停用角色"""
		role = await self.get(role_id)
		if not role:
			return False

		result = await self.update(role_id, {'is_active': False})
		return result is not None

	async def activate_role (self, role_id: int) -> bool:
		"""激活角色"""
		role = await self.get(role_id)
		if not role:
			return False

		result = await self.update(role_id, {'is_active': True})
		return result is not None

	async def get_users_by_role (self, role_id: int) -> List[int]:
		"""获取拥有该角色的用户ID列表（需要关联用户表）"""
		# 这里假设用户和角色有关联关系
		# 实际实现需要根据数据库设计调整

		# 示例代码
		# query = select(UserRole.user_id).where(
		#     UserRole.role_id == role_id
		# )
		# result = await self.session.execute(query)
		# return [row[0] for row in result.all()]

		return []  # 返回空列表，实际需要实现

	async def get_role_usage_statistics (self) -> Dict[str, Any]:
		"""获取角色使用情况统计"""
		# 这里需要统计每个角色分配给了多少用户
		# 实际实现需要根据数据库设计调整

		# 示例代码
		# query = select(
		#     SysRole.id,
		#     SysRole.name,
		#     func.count(UserRole.user_id).label('user_count')
		# ).join(
		#     UserRole, UserRole.role_id == SysRole.id, isouter=True
		# ).where(
		#     SysRole.is_active == True
		# ).group_by(
		#     SysRole.id, SysRole.name
		# ).order_by(
		#     func.count(UserRole.user_id).desc()
		# )

		# result = await self.session.execute(query)
		# rows = result.all()

		# return [
		#     {'role_id': row[0], 'role_name': row[1], 'user_count': row[2]}
		#     for row in rows
		# ]

		return {'statistics': []}  # 返回空字典，实际需要实现