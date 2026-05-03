# -*- coding: utf-8 -*-
"""
用户数据仓库
提供系统用户数据的统一访问接口
位置：shared/database/repositories/user_repo.py
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import SysUser, SysPermission
from shared.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class UserRepository:
	"""用户数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.user_repo = BaseRepository(session, SysUser)
		self.permission_repo = BaseRepository(session, SysPermission)

	# ==================== 基础CRUD操作 ====================

	async def create_user (self, data: Dict[str, Any]) -> SysUser:
		"""创建用户"""
		return await self.user_repo.create(data)

	async def get_user (self, user_id: str) -> Optional[SysUser]:
		"""根据ID获取用户"""
		return await self.user_repo.get(user_id)

	async def get_by_id (self, user_id: str) -> Optional[SysUser]:
		"""根据ID获取用户（get_user的别名，保持接口一致性）"""
		return await self.user_repo.get(user_id)

	async def update_user (self, user_id: str, data: Dict[str, Any]) -> Optional[SysUser]:
		"""更新用户"""
		return await self.user_repo.update(user_id, data)

	async def delete_user (self, user_id: str, soft: bool = True) -> bool:
		"""删除用户"""
		return await self.user_repo.delete(user_id, soft)

	async def get_user_by_username (self, username: str) -> Optional[SysUser]:
		"""根据用户名获取用户"""
		return await self.user_repo.get_by(username=username)

	async def get_user_by_email (self, email: str) -> Optional[SysUser]:
		"""根据邮箱获取用户"""
		return await self.user_repo.get_by(email=email)

	async def get_user_by_phone (self, phone: str) -> Optional[SysUser]:
		"""根据手机号获取用户"""
		return await self.user_repo.get_by(phone=phone)

	async def get_users (
			self,
			skip: int = 0,
			limit: int = 100,
			active_only: bool = True
	) -> List[SysUser]:
		"""获取用户列表"""
		filters = {}
		if active_only:
			filters['is_active'] = True

		return await self.user_repo.get_many(
			skip=skip,
			limit=limit,
			**filters
		)

	async def count_users (self, active_only: bool = True) -> int:
		"""统计用户数量"""
		filters = {}
		if active_only:
			filters['is_active'] = True

		return await self.user_repo.count(**filters)

	# ==================== 用户认证相关 ====================

	async def authenticate_user (self, username: str, password: str) -> Optional[SysUser]:
		"""用户认证"""
		user = await self.get_user_by_username(username)
		if user and user.password == password and user.is_active:
			return user
		return None

	async def update_last_login (self, user_id: str) -> bool:
		"""更新最后登录时间"""
		result = await self.update_user(user_id, {
			'last_login': datetime.now()
		})
		return result is not None

	async def update_password (self, user_id: str, new_password: str) -> bool:
		"""更新密码"""
		result = await self.update_user(user_id, {
			'password': new_password
		})
		return result is not None

	async def activate_user (self, user_id: str) -> bool:
		"""激活用户"""
		result = await self.update_user(user_id, {'is_active': True})
		return result is not None

	async def deactivate_user (self, user_id: str) -> bool:
		"""停用用户"""
		result = await self.update_user(user_id, {'is_active': False})
		return result is not None

	async def change_user_role (self, user_id: str, new_role: str) -> bool:
		"""更改用户角色"""
		result = await self.update_user(user_id, {'role': new_role})
		return result is not None

	# ==================== 用户搜索 ====================

	async def search_users (
			self,
			keyword: Optional[str] = None,
			role: Optional[str] = None,
			is_active: Optional[bool] = None,
			skip: int = 0,
			limit: int = 100
	) -> List[SysUser]:
		"""搜索用户"""
		# 构建查询
		query = select(SysUser)

		if keyword:
			query = query.where(
				or_(
					SysUser.username.like(f"%{keyword}%"),
					SysUser.real_name.like(f"%{keyword}%"),
					SysUser.email.like(f"%{keyword}%"),
					SysUser.phone.like(f"%{keyword}%")
				)
			)

		if role:
			query = query.where(SysUser.role == role)

		if is_active is not None:
			query = query.where(SysUser.is_active == is_active)

		# 排序和分页
		query = query.order_by(SysUser.created_at.desc())
		query = query.offset(skip).limit(limit)

		# 执行查询
		result = await self.session.execute(query)
		return result.scalars().all()

	async def search_users_count (
			self,
			keyword: Optional[str] = None,
			role: Optional[str] = None,
			is_active: Optional[bool] = None
	) -> int:
		"""统计搜索结果数量"""
		# 构建查询
		query = select(func.count()).select_from(SysUser)

		if keyword:
			query = query.where(
				or_(
					SysUser.username.like(f"%{keyword}%"),
					SysUser.real_name.like(f"%{keyword}%"),
					SysUser.email.like(f"%{keyword}%"),
					SysUser.phone.like(f"%{keyword}%")
				)
			)

		if role:
			query = query.where(SysUser.role == role)

		if is_active is not None:
			query = query.where(SysUser.is_active == is_active)

		# 执行查询
		result = await self.session.execute(query)
		return result.scalar() or 0

	# ==================== 用户统计 ====================

	async def get_user_statistics (self) -> Dict[str, Any]:
		"""获取用户统计信息"""
		# 总用户数
		total_count = await self.count_users(active_only=False)

		# 活跃用户数
		active_count = await self.count_users(active_only=True)

		# 按角色统计
		role_stats = await self.session.execute(
			select(
				SysUser.role,
				func.count(SysUser.id).label('count'),
				func.sum(case(
					(SysUser.is_active == True, 1),
					else_=0
				)).label('active')
			).group_by(
				SysUser.role
			).order_by(
				func.count(SysUser.id).desc()
			)
		)

		role_stats_dict = {}
		for row in role_stats.all():
			role_stats_dict[row.role] = {
				'total': row.count,
				'active': row.active or 0,
				'inactive': row.count - (row.active or 0)
			}

		# 最近注册用户数（最近30天）
		thirty_days_ago = datetime.now() - timedelta(days=30)
		recent_query = select(func.count()).select_from(SysUser).where(
			and_(
				SysUser.created_at >= thirty_days_ago,
				SysUser.is_active == True
			)
		)
		recent_result = await self.session.execute(recent_query)
		recent_count = recent_result.scalar() or 0

		# 最近登录用户数（最近7天）
		seven_days_ago = datetime.now() - timedelta(days=7)
		recent_login_query = select(func.count()).select_from(SysUser).where(
			and_(
				SysUser.last_login >= seven_days_ago,
				SysUser.is_active == True
			)
		)
		recent_login_result = await self.session.execute(recent_login_query)
		recent_login_count = recent_login_result.scalar() or 0

		return {
			'total_users': total_count,
			'active_users': active_count,
			'inactive_users': total_count - active_count,
			'role_statistics': role_stats_dict,
			'recent_registered': recent_count,
			'recent_logged_in': recent_login_count
		}

	async def get_user_growth_trend (
			self,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""获取用户增长趋势"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		query = select(
			func.date(SysUser.created_at).label('date'),
			func.count(SysUser.id).label('new_users'),
			func.sum(case(
				(SysUser.is_active == True, 1),
				else_=0
			)).label('active_new_users')
		).where(
			SysUser.created_at >= start_date
		).group_by(
			func.date(SysUser.created_at)
		).order_by(
			func.date(SysUser.created_at).asc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		# 按日期组织数据
		date_dict = {}
		for row in rows:
			date_str = row.date.strftime('%Y-%m-%d')
			date_dict[date_str] = {
				'date': row.date,
				'new_users': row.new_users or 0,
				'active_new_users': row.active_new_users or 0
			}

		# 转换为列表并填充缺失日期
		trend_list = []
		current_date = start_date
		while current_date <= end_date:
			date_str = current_date.strftime('%Y-%m-%d')
			if date_str in date_dict:
				trend_list.append(date_dict[date_str])
			else:
				trend_list.append({
					'date': current_date,
					'new_users': 0,
					'active_new_users': 0
				})
			current_date += timedelta(days=1)

		# 计算累计用户数
		cumulative_total = 0
		cumulative_active = 0
		for item in trend_list:
			cumulative_total += item['new_users']
			cumulative_active += item['active_new_users']
			item['cumulative_total'] = cumulative_total
			item['cumulative_active'] = cumulative_active

		return trend_list

	async def get_user_activity_statistics (
			self,
			days: int = 30
	) -> Dict[str, Any]:
		"""获取用户活跃度统计"""
		end_date = datetime.now()
		start_date = end_date - timedelta(days=days)

		# 登录用户统计
		login_stats = await self.session.execute(
			select(
				func.date(SysUser.last_login).label('date'),
				func.count(SysUser.id).label('login_count')
			).where(
				and_(
					SysUser.last_login >= start_date,
					SysUser.last_login <= end_date,
					SysUser.is_active == True
				)
			).group_by(
				func.date(SysUser.last_login)
			).order_by(
				func.date(SysUser.last_login).desc()
			)
		)

		login_days = {}
		for row in login_stats.all():
			if row.date:
				date_str = row.date.strftime('%Y-%m-%d')
				login_days[date_str] = row.login_count

		# 计算活跃天数
		active_days = len(login_days)
		avg_daily_login = sum(login_days.values()) / days if days > 0 else 0

		# 用户活跃度等级
		# 高活跃：最近7天登录≥5天
		# 中活跃：最近7天登录2-4天
		# 低活跃：最近7天登录1天
		# 不活跃：最近7天未登录

		seven_days_ago = end_date - timedelta(days=7)

		# 获取最近7天登录情况
		recent_login_stats = await self.session.execute(
			select(
				SysUser.id,
				func.count(func.date(SysUser.last_login)).label('login_days')
			).where(
				and_(
					SysUser.last_login >= seven_days_ago,
					SysUser.last_login <= end_date,
					SysUser.is_active == True
				)
			).group_by(
				SysUser.id
			)
		)

		high_active = 0
		medium_active = 0
		low_active = 0

		for row in recent_login_stats.all():
			login_days = row.login_days or 0
			if login_days >= 5:
				high_active += 1
			elif login_days >= 2:
				medium_active += 1
			elif login_days >= 1:
				low_active += 1

		# 不活跃用户 = 总活跃用户 - 最近7天登录过的用户
		total_active = await self.count_users(active_only=True)
		inactive = total_active - (high_active + medium_active + low_active)

		return {
			'period_days': days,
			'active_days': active_days,
			'avg_daily_login': avg_daily_login,
			'activity_levels': {
				'high_active': high_active,
				'medium_active': medium_active,
				'low_active': low_active,
				'inactive': inactive
			},
			'total_active_users': total_active,
			'login_stats': login_days
		}

	# ==================== 用户权限相关 ====================

	async def get_user_permissions (self, user_id: str) -> List[SysPermission]:
		"""获取用户权限"""
		query = select(SysPermission).where(
			SysPermission.user_id == user_id
		).order_by(SysPermission.module.asc())
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_user_with_permissions (self, user_id: str) -> Optional[Dict[str, Any]]:
		"""获取用户及其权限"""
		user = await self.get_user(user_id)
		if not user:
			return None

		permissions = await self.get_user_permissions(user_id)

		return {
			'user': user,
			'permissions': permissions
		}

	async def has_permission (
			self,
			user_id: str,
			module: str,
			permission_type: str
	) -> bool:
		"""检查用户是否有特定权限"""
		query = select(SysPermission).where(
			and_(
				SysPermission.user_id == user_id,
				SysPermission.module == module
			)
		)
		result = await self.session.execute(query)
		permission = result.scalar_one_or_none()

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

	async def grant_permission (
			self,
			user_id: str,
			module: str,
			can_read: bool = False,
			can_write: bool = False,
			can_execute: bool = False
	) -> bool:
		"""授予用户权限"""
		# 检查权限是否已存在
		query = select(SysPermission).where(
			and_(
				SysPermission.user_id == user_id,
				SysPermission.module == module
			)
		)
		result = await self.session.execute(query)
		existing = result.scalar_one_or_none()

		if existing:
			# 更新现有权限
			update_data = {}
			if can_read is not None:
				update_data['can_read'] = can_read
			if can_write is not None:
				update_data['can_write'] = can_write
			if can_execute is not None:
				update_data['can_execute'] = can_execute

			result = await self.permission_repo.update(existing.id, update_data)
		else:
			# 创建新权限
			permission_data = {
				'user_id': user_id,
				'module': module,
				'can_read': can_read,
				'can_write': can_write,
				'can_execute': can_execute
			}
			result = await self.permission_repo.create(permission_data)

		return result is not None

	async def revoke_permission (
			self,
			user_id: str,
			module: str,
			permission_type: Optional[str] = None
	) -> bool:
		"""撤销用户权限"""
		query = select(SysPermission).where(
			and_(
				SysPermission.user_id == user_id,
				SysPermission.module == module
			)
		)
		result = await self.session.execute(query)
		permission = result.scalar_one_or_none()

		if not permission:
			return False

		if permission_type is None:
			# 撤销所有权限（删除记录）
			return await self.permission_repo.delete(permission.id, soft=False)
		else:
			# 撤销特定权限
			update_data = {}
			if permission_type == 'read':
				update_data['can_read'] = False
			elif permission_type == 'write':
				update_data['can_write'] = False
			elif permission_type == 'execute':
				update_data['can_execute'] = False

			result = await self.permission_repo.update(permission.id, update_data)
			return result is not None

	async def revoke_all_permissions (self, user_id: str) -> int:
		"""撤销用户所有权限"""
		permissions = await self.get_user_permissions(user_id)

		revoked_count = 0
		for permission in permissions:
			success = await self.permission_repo.delete(permission.id, soft=False)
			if success:
				revoked_count += 1

		return revoked_count

	# ==================== 批量操作 ====================

	async def batch_create_users (
			self,
			users_data: List[Dict[str, Any]]
	) -> List[SysUser]:
		"""批量创建用户"""
		return await self.user_repo.batch_create(users_data)

	async def batch_upsert_users (
			self,
			users_data: List[Dict[str, Any]],
			match_fields: Optional[List[str]] = None
	) -> List[SysUser]:
		"""批量插入或更新用户"""
		if match_fields is None:
			match_fields = ['username']
		return await self.user_repo.batch_upsert(match_fields, users_data)

	async def batch_update_user_status (
			self,
			user_ids: List[str],
			is_active: bool
	) -> int:
		"""批量更新用户状态"""
		updated_count = 0

		for user_id in user_ids:
			result = await self.update_user(user_id, {'is_active': is_active})
			if result:
				updated_count += 1

		return updated_count

	async def batch_grant_permissions (
			self,
			permissions_data: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""批量授予权限"""
		success_count = 0
		failed_count = 0

		for perm_data in permissions_data:
			user_id = perm_data.get('user_id')
			module = perm_data.get('module')

			if not user_id or not module:
				failed_count += 1
				continue

			try:
				can_read = perm_data.get('can_read', False)
				can_write = perm_data.get('can_write', False)
				can_execute = perm_data.get('can_execute', False)

				success = await self.grant_permission(
					user_id, module, can_read, can_write, can_execute
				)

				if success:
					success_count += 1
				else:
					failed_count += 1
			except Exception as e:
				logger.error(f"授予权限失败: {str(e)}")
				failed_count += 1

		return {
			'success': success_count,
			'failed': failed_count,
			'total': len(permissions_data)
		}

	# ==================== 数据导出 ====================

	async def export_users (
			self,
			user_ids: Optional[List[str]] = None,
			include_permissions: bool = False
	) -> List[Dict[str, Any]]:
		"""导出用户数据"""
		if user_ids:
			users = []
			for user_id in user_ids:
				user = await self.get_user(user_id)
				if user:
					users.append(user)
		else:
			users = await self.get_users(active_only=False, limit=1000)

		export_data = []
		for user in users:
			user_data = {
				'id': user.id,
				'username': user.username,
				'email': user.email,
				'phone': user.phone,
				'real_name': user.real_name,
				'role': user.role,
				'is_active': user.is_active,
				'last_login': user.last_login.isoformat() if user.last_login else None,
				'created_at': user.created_at.isoformat() if user.created_at else None,
				'updated_at': user.updated_at.isoformat() if user.updated_at else None
			}

			if include_permissions:
				permissions = await self.get_user_permissions(user.id)
				user_data['permissions'] = [
					{
						'module': p.module,
						'can_read': p.can_read,
						'can_write': p.can_write,
						'can_execute': p.can_execute
					}
					for p in permissions
				]

			export_data.append(user_data)

		return export_data

	async def delete_inactive_users (
			self,
			days: int = 180
	) -> int:
		"""删除长期不活跃的用户"""
		cutoff_time = datetime.now() - timedelta(days=days)

		# 获取长期不活跃且未激活的用户
		query = select(SysUser.id).where(
			and_(
				SysUser.is_active == False,
				or_(
					SysUser.last_login.is_(None),
					SysUser.last_login < cutoff_time
				)
			)
		)

		result = await self.session.execute(query)
		inactive_user_ids = [row[0] for row in result.all()]

		# 批量删除
		deleted_count = 0
		for user_id in inactive_user_ids:
			success = await self.delete_user(user_id, soft=False)
			if success:
				deleted_count += 1

		return deleted_count

	async def get_user_summary (self) -> Dict[str, Any]:
		"""获取用户数据摘要"""
		# 基础统计
		stats = await self.get_user_statistics()

		# 活跃度统计
		activity_stats = await self.get_user_activity_statistics(30)

		# 角色分布
		role_distribution = {}
		for role, role_stats in stats['role_statistics'].items():
			role_distribution[role] = {
				'total': role_stats['total'],
				'active': role_stats['active'],
				'percentage': role_stats['active'] / stats['active_users'] * 100
				if stats['active_users'] > 0 else 0
			}

		# 最近注册的用户
		recent_users = await self.get_users(skip=0, limit=10)

		return {
			'statistics': stats,
			'activity_statistics': activity_stats,
			'role_distribution': role_distribution,
			'recent_users': [
				{
					'id': user.id,
					'username': user.username,
					'real_name': user.real_name,
					'role': user.role,
					'created_at': user.created_at,
					'last_login': user.last_login
				}
				for user in recent_users
			],
			'timestamp': datetime.now().isoformat()
		}