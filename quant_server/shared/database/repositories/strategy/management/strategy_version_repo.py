# -*- coding: utf-8 -*-
"""
策略版本管理表Repository
位置：shared/database/repositories/strategy/strategy_version_repo.py
"""
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, between, case
from sqlalchemy.orm import joinedload, load_only

from quant_server.core.exceptions import ValidationError
from quant_server.shared.database.models.business_models import StrategyVersion, Strategy, SysUser
from quant_server.shared.database.repositories import NotFoundError
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError
from quant_server.shared.database.repositories.types import (
	RepositoryResult, PaginationParams, PaginationResult,
	FilterCondition, SortCondition, QueryParams
)


class StrategyVersionRepository(BaseRepository[StrategyVersion]):
	"""策略版本管理Repository"""

	def __init__ (self, session: AsyncSession):
		"""初始化Repository"""
		super().__init__(session, StrategyVersion)

	async def create_version (
			self,
			strategy_id: str,
			version_number: str,
			code_content: str,
			version_name: Optional[str] = None,
			description: Optional[str] = None,
			parameters: Optional[Dict[str, Any]] = None,
			is_current: bool = False,
			created_by: Optional[int] = None
	) -> StrategyVersion:
		"""
		创建策略版本

		Args:
			strategy_id: 策略ID
			version_number: 版本号
			code_content: 代码内容
			version_name: 版本名称
			description: 版本描述
			parameters: 版本参数
			is_current: 是否为当前版本
			created_by: 创建人ID

		Returns:
			策略版本记录
		"""
		try:
			# 如果需要设置为当前版本，先将其他版本设为非当前
			if is_current:
				await self.clear_current_version(strategy_id)

			data = {
				"strategy_id": strategy_id,
				"version_number": version_number,
				"version_name": version_name or f"Version {version_number}",
				"description": description,
				"code_content": code_content,
				"parameters": parameters or {},
				"is_current": is_current,
				"created_by": created_by
			}

			return await self.create(data)
		except Exception as e:
			raise RepositoryError(f"创建策略版本失败: {str(e)}")

	async def get_by_strategy_id (
			self,
			strategy_id: str,
			include_code: bool = False,
			limit: int = 100
	) -> List[StrategyVersion]:
		"""
		根据策略ID获取版本列表

		Args:
			strategy_id: 策略ID
			include_code: 是否包含代码内容
			limit: 限制记录数

		Returns:
			策略版本列表
		"""
		try:
			if include_code:
				query = select(self.model)
			else:
				# 不包含代码内容以节省带宽
				query = select(
					self.model.id,
					self.model.strategy_id,
					self.model.version_number,
					self.model.version_name,
					self.model.description,
					self.model.parameters,
					self.model.is_current,
					self.model.created_by,
					self.model.created_at
				)

			query = query.where(
				self.model.strategy_id == strategy_id
			).order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)

			if include_code:
				return result.scalars().all()
			else:
				# 手动构建对象
				rows = result.fetchall()
				versions = []
				for row in rows:
					version = StrategyVersion()
					for i, column in enumerate(row._fields):
						setattr(version, column, row[i])
					versions.append(version)
				return versions
		except Exception as e:
			raise RepositoryError(f"获取策略版本列表失败: {str(e)}")

	async def get_by_version_number (
			self,
			strategy_id: str,
			version_number: str
	) -> Optional[StrategyVersion]:
		"""
		根据版本号获取策略版本

		Args:
			strategy_id: 策略ID
			version_number: 版本号

		Returns:
			策略版本记录或None
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.version_number == version_number
				)
			)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取策略版本失败: {str(e)}")

	async def get_current_version (
			self,
			strategy_id: str
	) -> Optional[StrategyVersion]:
		"""
		获取策略的当前版本

		Args:
			strategy_id: 策略ID

		Returns:
			当前策略版本或None
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.is_current == True
				)
			)

			result = await self.session.execute(query)
			return result.scalar_one_or_none()
		except Exception as e:
			raise RepositoryError(f"获取当前版本失败: {str(e)}")

	async def set_current_version (
			self,
			strategy_id: str,
			version_id: int
	) -> Optional[StrategyVersion]:
		"""
		设置当前版本

		Args:
			strategy_id: 策略ID
			version_id: 版本ID

		Returns:
			更新后的策略版本
		"""
		try:
			# 首先清除所有当前版本标记
			await self.clear_current_version(strategy_id)

			# 设置指定版本为当前版本
			version = await self.get(version_id)
			if version and version.strategy_id == strategy_id:
				return await self.update(version_id, {
					"is_current": True,
					"updated_at": datetime.now()
				})

			return None
		except Exception as e:
			raise RepositoryError(f"设置当前版本失败: {str(e)}")

	async def clear_current_version (self, strategy_id: str) -> int:
		"""
		清除当前版本标记

		Args:
			strategy_id: 策略ID

		Returns:
			更新的记录数
		"""
		try:
			query = select(self.model).where(
				and_(
					self.model.strategy_id == strategy_id,
					self.model.is_current == True
				)
			)

			result = await self.session.execute(query)
			current_versions = result.scalars().all()

			updated_count = 0
			for version in current_versions:
				await self.update(version.id, {
					"is_current": False,
					"updated_at": datetime.now()
				})
				updated_count += 1

			return updated_count
		except Exception as e:
			raise RepositoryError(f"清除当前版本失败: {str(e)}")

	async def get_version_history (
			self,
			strategy_id: str,
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			limit: int = 50
	) -> List[StrategyVersion]:
		"""
		获取版本历史

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期
			limit: 限制记录数

		Returns:
			版本历史列表
		"""
		try:
			query = select(self.model).where(
				self.model.strategy_id == strategy_id
			)

			if start_date:
				query = query.where(self.model.created_at >= start_date)
			if end_date:
				query = query.where(self.model.created_at <= end_date)

			query = query.order_by(
				desc(self.model.created_at)
			).limit(limit)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取版本历史失败: {str(e)}")

	async def compare_versions (
			self,
			version_id_1: int,
			version_id_2: int
	) -> Dict[str, Any]:
		"""
		比较两个版本

		Args:
			version_id_1: 版本1 ID
			version_id_2: 版本2 ID

		Returns:
			版本比较结果
		"""
		try:
			version1 = await self.get(version_id_1)
			version2 = await self.get(version_id_2)

			if not version1 or not version2:
				raise NotFoundError("版本不存在")

			if version1.strategy_id != version2.strategy_id:
				raise ValidationError("不能比较不同策略的版本")

			# 比较代码内容（简单比较）
			code_same = version1.code_content == version2.code_content

			# 比较参数
			params1 = version1.parameters or {}
			params2 = version2.parameters or {}

			param_differences = {}
			all_params = set(params1.keys()) | set(params2.keys())

			for param in all_params:
				val1 = params1.get(param)
				val2 = params2.get(param)
				if val1 != val2:
					param_differences[param] = {
						"version1": val1,
						"version2": val2,
						"changed": True
					}

			return {
				"strategy_id": version1.strategy_id,
				"version1": {
					"id": version1.id,
					"version_number": version1.version_number,
					"version_name": version1.version_name,
					"created_at": version1.created_at
				},
				"version2": {
					"id": version2.id,
					"version_number": version2.version_number,
					"version_name": version2.version_name,
					"created_at": version2.created_at
				},
				"comparison": {
					"code_same": code_same,
					"parameter_differences": param_differences,
					"total_differences": len(param_differences) + (0 if code_same else 1)
				}
			}
		except Exception as e:
			if isinstance(e, (NotFoundError, ValidationError)):
				raise e
			raise RepositoryError(f"比较版本失败: {str(e)}")

	async def rollback_to_version (
			self,
			strategy_id: str,
			version_id: int
	) -> Optional[StrategyVersion]:
		"""
		回滚到指定版本

		Args:
			strategy_id: 策略ID
			version_id: 版本ID

		Returns:
			设置为当前版本的回滚版本
		"""
		try:
			version = await self.get(version_id)
			if not version or version.strategy_id != strategy_id:
				raise NotFoundError(f"版本不存在或不属于指定策略")

			# 设置该版本为当前版本
			return await self.set_current_version(strategy_id, version_id)
		except Exception as e:
			if isinstance(e, NotFoundError):
				raise e
			raise RepositoryError(f"回滚版本失败: {str(e)}")

	async def get_version_statistics (
			self,
			strategy_id: Optional[str] = None,
			created_by: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取版本统计信息

		Args:
			strategy_id: 策略ID
			created_by: 创建人ID

		Returns:
			版本统计信息
		"""
		try:
			query = select(
				func.count().label("total_versions"),
				func.count(
					case([(self.model.is_current == True, 1)], else_=None)
				).label("current_versions"),
				self.model.strategy_id
			).group_by(
				self.model.strategy_id
			)

			if strategy_id:
				query = query.where(self.model.strategy_id == strategy_id)
			if created_by:
				query = query.where(self.model.created_by == created_by)

			result = await self.session.execute(query)
			rows = result.fetchall()

			total_versions = 0
			current_versions = 0
			versions_by_strategy = {}

			for row in rows:
				total_versions += row.total_versions or 0
				current_versions += row.current_versions or 0

				strategy_id_val = row.strategy_id
				versions_by_strategy[strategy_id_val] = {
					"total_versions": row.total_versions or 0,
					"current_versions": row.current_versions or 0
				}

			return {
				"total_versions": total_versions,
				"current_versions": current_versions,
				"historical_versions": total_versions - current_versions,
				"versions_by_strategy": versions_by_strategy
			}
		except Exception as e:
			raise RepositoryError(f"获取版本统计失败: {str(e)}")