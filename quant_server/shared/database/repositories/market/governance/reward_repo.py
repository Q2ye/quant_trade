# -*- coding: utf-8 -*-
"""
股票分红送股数据仓库
提供股票分红送股数据的统一访问接口
位置：shared/database/repositories/market/governance/reward_repository.py

注意：此文件由reward_repo.py重命名而来，采用继承BaseRepository方式
保持与设计文档命名一致：reward_repository.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, distinct

from quant_server.shared.database.repositories.base import BaseRepository
from quant_server.shared.database.models.data_models import StkReward


class RewardRepository(BaseRepository[StkReward]):
	"""分红送股数据Repository - 继承BaseRepository"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化分红送股Repository

		Args:
			session: 数据库会话，提供数据访问上下文
		"""
		super().__init__(session, StkReward)

	# ==================== 基础CRUD操作 ====================
	# 继承自BaseRepository，包含：get, create, update, delete, get_by, get_many, get_all, count, exists等

	# ==================== 业务查询方法 ====================

	async def get_by_ts_code (
			self,
			ts_code: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			limit: int = 100
	) -> List[StkReward]:
		"""
		根据股票代码获取分红送股记录

		Args:
			ts_code: 股票代码
			start_date: 开始日期（可选）
			end_date: 结束日期（可选）
			limit: 返回记录数限制

		Returns:
			分红送股记录列表
		"""
		filters = [self.model.ts_code == ts_code]

		if start_date:
			filters.append(self.model.ann_date >= start_date)
		if end_date:
			filters.append(self.model.ann_date <= end_date)

		return await self.get_many(
			*filters,
			limit=limit,
			order_by=self.model.ann_date.desc()
		)

	async def get_by_manager_id (
			self,
			manager_id: int,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None
	) -> List[StkReward]:
		"""
		根据管理层ID获取分红送股记录

		Args:
			manager_id: 管理层ID
			start_date: 开始日期（可选）
			end_date: 结束日期（可选）

		Returns:
			分红送股记录列表
		"""
		filters = [self.model.manager_id == manager_id]

		if start_date:
			filters.append(self.model.ann_date >= start_date)
		if end_date:
			filters.append(self.model.ann_date <= end_date)

		return await self.get_many(
			*filters,
			order_by=self.model.ann_date.desc()
		)

	async def get_by_date_range (
			self,
			start_date: date,
			end_date: date,
			ts_codes: Optional[List[str]] = None
	) -> List[StkReward]:
		"""
		根据日期范围获取分红送股记录

		Args:
			start_date: 开始日期
			end_date: 结束日期
			ts_codes: 股票代码列表（可选）

		Returns:
			分红送股记录列表
		"""
		filters = [
			self.model.ann_date >= start_date,
			self.model.ann_date <= end_date
		]

		if ts_codes:
			filters.append(self.model.ts_code.in_(ts_codes))

		return await self.get_many(
			*filters,
			order_by=self.model.ann_date.desc()
		)

	async def get_latest_rewards (
			self,
			ts_code: str,
			n: int = 5
	) -> List[StkReward]:
		"""
		获取最近N次分红送股记录

		Args:
			ts_code: 股票代码
			n: 记录数量

		Returns:
			最近的分红送股记录列表
		"""
		return await self.get_many(
			self.model.ts_code == ts_code,
			limit=n,
			order_by=self.model.ann_date.desc()
		)

	async def get_total_rewards_by_year (
			self,
			ts_code: str,
			year: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取年度分红送股总额

		Args:
			ts_code: 股票代码
			year: 年份（可选，为空则返回所有年份）

		Returns:
			年度分红统计信息
		"""
		query = select(
			func.extract('year', self.model.ann_date).label('year'),
			func.sum(self.model.reward).label('total_reward'),
			func.sum(self.model.hold_vol).label('total_hold_vol'),
			func.count(self.model.id).label('count')
		).where(
			self.model.ts_code == ts_code
		)

		if year:
			query = query.where(
				func.extract('year', self.model.ann_date) == year
			)

		query = query.group_by(
			func.extract('year', self.model.ann_date)
		).order_by(
			func.extract('year', self.model.ann_date).desc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		if year and rows:
			row = rows[0]
			return {
				'year': int(row.year) if row.year else None,
				'total_reward': float(row.total_reward) if row.total_reward else 0,
				'total_hold_vol': row.total_hold_vol or 0,
				'count': row.count or 0
			}

		return {
			'yearly_stats': [
				{
					'year': int(row.year) if row.year else None,
					'total_reward': float(row.total_reward) if row.total_reward else 0,
					'total_hold_vol': row.total_hold_vol or 0,
					'count': row.count or 0
				}
				for row in rows
			]
		}

	async def get_reward_statistics (
			self,
			ts_code: Optional[str] = None,
			year: Optional[int] = None
	) -> Dict[str, Any]:
		"""
		获取分红送股统计信息

		Args:
			ts_code: 股票代码（可选）
			year: 年份（可选）

		Returns:
			分红统计信息
		"""
		# 基础查询
		query = select(
			func.count(self.model.id).label('total_count'),
			func.sum(self.model.reward).label('total_reward'),
			func.avg(self.model.reward).label('avg_reward'),
			func.min(self.model.reward).label('min_reward'),
			func.max(self.model.reward).label('max_reward')
		)

		filters = []
		if ts_code:
			filters.append(self.model.ts_code == ts_code)
		if year:
			filters.append(func.extract('year', self.model.ann_date) == year)

		if filters:
			query = query.where(and_(*filters))

		result = await self.session.execute(query)
		row = result.first()

		if not row:
			return {}

		return {
			'ts_code': ts_code,
			'year': year,
			'total_count': row.total_count or 0,
			'total_reward': float(row.total_reward) if row.total_reward else 0,
			'avg_reward': float(row.avg_reward) if row.avg_reward else 0,
			'min_reward': float(row.min_reward) if row.min_reward else 0,
			'max_reward': float(row.max_reward) if row.max_reward else 0
		}

	async def get_top_reward_stocks (
			self,
			year: Optional[int] = None,
			top_n: int = 20
	) -> List[Dict[str, Any]]:
		"""
		获取分红总额最高的股票

		Args:
			year: 年份（可选）
			top_n: 返回数量

		Returns:
			分红总额最高的股票列表
		"""
		query = select(
			self.model.ts_code,
			func.sum(self.model.reward).label('total_reward'),
			func.count(self.model.id).label('count')
		)

		if year:
			query = query.where(
				func.extract('year', self.model.ann_date) == year
			)

		query = query.group_by(
			self.model.ts_code
		).order_by(
			func.sum(self.model.reward).desc()
		).limit(top_n)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'ts_code': row[0],
				'total_reward': float(row[1]) if row[1] else 0,
				'count': row[2] or 0
			}
			for row in rows
		]

	async def get_hold_volume_statistics (
			self,
			ts_code: str
	) -> Dict[str, Any]:
		"""
		获取持股数量统计

		Args:
			ts_code: 股票代码

		Returns:
			持股数量统计信息
		"""
		result = await self.session.execute(
			select(
				func.sum(self.model.hold_vol).label('total_hold_vol'),
				func.avg(self.model.hold_vol).label('avg_hold_vol'),
				func.min(self.model.hold_vol).label('min_hold_vol'),
				func.max(self.model.hold_vol).label('max_hold_vol')
			).where(
				self.model.ts_code == ts_code
			)
		)

		row = result.first()
		if not row:
			return {}

		return {
			'ts_code': ts_code,
			'total_hold_vol': row.total_hold_vol or 0,
			'avg_hold_vol': float(row.avg_hold_vol) if row.avg_hold_vol else 0,
			'min_hold_vol': row.min_hold_vol or 0,
			'max_hold_vol': row.max_hold_vol or 0
		}

	async def get_reward_trend (
			self,
			ts_code: str,
			years: int = 5
	) -> List[Dict[str, Any]]:
		"""
		获取分红趋势

		Args:
			ts_code: 股票代码
			years: 统计年数

		Returns:
			分红趋势数据
		"""
		current_year = datetime.now().year
		start_year = current_year - years + 1

		query = select(
			func.extract('year', self.model.ann_date).label('year'),
			func.sum(self.model.reward).label('total_reward'),
			func.avg(self.model.reward).label('avg_reward'),
			func.count(self.model.id).label('count')
		).where(
			and_(
				self.model.ts_code == ts_code,
				func.extract('year', self.model.ann_date) >= start_year,
				func.extract('year', self.model.ann_date) <= current_year
			)
		).group_by(
			func.extract('year', self.model.ann_date)
		).order_by(
			func.extract('year', self.model.ann_date).asc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'year': int(row.year) if row.year else None,
				'total_reward': float(row.total_reward) if row.total_reward else 0,
				'avg_reward': float(row.avg_reward) if row.avg_reward else 0,
				'count': row.count or 0
			}
			for row in rows
		]

	async def get_manager_rewards_summary (
			self,
			manager_id: int
	) -> Dict[str, Any]:
		"""
		获取管理层的分红送股汇总

		Args:
			manager_id: 管理层ID

		Returns:
			管理层的分红汇总信息
		"""
		result = await self.session.execute(
			select(
				func.sum(self.model.reward).label('total_reward'),
				func.avg(self.model.reward).label('avg_reward'),
				func.sum(self.model.hold_vol).label('total_hold_vol'),
				func.count(self.model.id).label('count'),
				func.count(func.distinct(self.model.ts_code)).label('stock_count')
			).where(
				self.model.manager_id == manager_id
			)
		)

		row = result.first()
		if not row:
			return {}

		return {
			'manager_id': manager_id,
			'total_reward': float(row.total_reward) if row.total_reward else 0,
			'avg_reward': float(row.avg_reward) if row.avg_reward else 0,
			'total_hold_vol': row.total_hold_vol or 0,
			'count': row.count or 0,
			'stock_count': row.stock_count or 0
		}

	async def get_stocks_by_reward_range (
			self,
			min_reward: Optional[float] = None,
			max_reward: Optional[float] = None,
			year: Optional[int] = None,
			limit: int = 100
	) -> List[Dict[str, Any]]:
		"""
		根据分红金额范围获取股票

		Args:
			min_reward: 最小分红金额（可选）
			max_reward: 最大分红金额（可选）
			year: 年份（可选）
			limit: 返回记录数限制

		Returns:
			符合条件股票的分红信息
		"""
		query = select(
			self.model.ts_code,
			func.sum(self.model.reward).label('total_reward'),
			func.avg(self.model.reward).label('avg_reward'),
			func.count(self.model.id).label('count')
		)

		filters = []
		if min_reward is not None:
			filters.append(self.model.reward >= min_reward)
		if max_reward is not None:
			filters.append(self.model.reward <= max_reward)
		if year:
			filters.append(func.extract('year', self.model.ann_date) == year)

		if filters:
			query = query.where(and_(*filters))

		query = query.group_by(
			self.model.ts_code
		).order_by(
			func.sum(self.model.reward).desc()
		).limit(limit)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'ts_code': row[0],
				'total_reward': float(row[1]) if row[1] else 0,
				'avg_reward': float(row[2]) if row[2] else 0,
				'count': row[3] or 0
			}
			for row in rows
		]

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[StkReward]:
		"""
		批量创建分红送股记录

		Args:
			data_list: 分红送股记录数据列表

		Returns:
			创建的StkReward对象列表
		"""
		return await super().batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['ts_code', 'ann_date', 'end_date', 'manager_id']
	) -> List[StkReward]:
		"""
		批量插入或更新分红送股记录

		Args:
			data_list: 分红送股记录数据列表
			match_fields: 匹配字段，用于判断记录是否存在

		Returns:
			StkReward对象列表
		"""
		# 注意：继承的batch_upsert参数顺序不同，需要调整
		return await super().batch_upsert(match_fields, data_list)

	async def get_reward_summary (self) -> Dict[str, Any]:
		"""
		获取分红送股数据摘要

		Returns:
			分红送股数据摘要信息
		"""
		# 总记录数
		total_count = await self.count()

		# 涉及股票数量
		stock_count = await self.session.execute(
			select(func.count(func.distinct(self.model.ts_code)))
		)
		stock_count_value = stock_count.scalar() or 0

		# 涉及管理层数量
		manager_count = await self.session.execute(
			select(func.count(func.distinct(self.model.manager_id)))
		)
		manager_count_value = manager_count.scalar() or 0

		# 分红总额
		total_reward = await self.session.execute(
			select(func.sum(self.model.reward))
		)
		total_reward_value = total_reward.scalar() or 0

		# 持股总额
		total_hold_vol = await self.session.execute(
			select(func.sum(self.model.hold_vol))
		)
		total_hold_vol_value = total_hold_vol.scalar() or 0

		# 年份分布
		year_dist = await self.session.execute(
			select(
				func.extract('year', self.model.ann_date).label('year'),
				func.count(self.model.id).label('count'),
				func.sum(self.model.reward).label('total_reward')
			).group_by(
				func.extract('year', self.model.ann_date)
			).order_by(
				func.extract('year', self.model.ann_date).desc()
			).limit(10)
		)

		year_stats = [
			{
				'year': int(row.year) if row.year else None,
				'count': row.count or 0,
				'total_reward': float(row.total_reward) if row.total_reward else 0
			}
			for row in year_dist.all()
		]

		return {
			'total_count': total_count,
			'stock_count': stock_count_value,
			'manager_count': manager_count_value,
			'total_reward': float(total_reward_value),
			'total_hold_vol': total_hold_vol_value,
			'year_stats': year_stats
		}