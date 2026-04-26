# -*- coding: utf-8 -*-
"""
持仓快照数据仓库
提供用户持仓快照数据的统一访问接口
位置：shared/database/repositories/trading/position/position_snapshot_repo.py
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import PositionSnapshot
from quant_server.shared.database.repositories.base import BaseRepository


class PositionSnapshotRepository(BaseRepository[PositionSnapshot]):
	"""持仓快照数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, PositionSnapshot)

	async def get_daily_snapshots (
			self,
			user_id: str,
			account_id: str,
			start_date: date,
			end_date: date
	) -> List[PositionSnapshot]:
		"""
		获取指定时间段内的每日持仓快照

		Args:
			user_id: 用户ID
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			持仓快照列表
		"""
		return await self.get_many(
			and_(
				PositionSnapshot.user_id == user_id,
				PositionSnapshot.account_id == account_id,
				PositionSnapshot.snapshot_date >= start_date,
				PositionSnapshot.snapshot_date <= end_date
			),
			order_by=PositionSnapshot.snapshot_date.desc()
		)

	async def get_account_snapshot_by_date (
			self,
			account_id: str,
			snapshot_date: date
	) -> List[PositionSnapshot]:
		"""
		获取指定账户在指定日期的持仓快照

		Args:
			account_id: 账户ID
			snapshot_date: 快照日期

		Returns:
			持仓快照列表
		"""
		return await self.get_many(
			and_(
				PositionSnapshot.account_id == account_id,
				PositionSnapshot.snapshot_date == snapshot_date
			),
			order_by=PositionSnapshot.ts_code.asc()
		)

	async def get_latest_snapshot (
			self,
			user_id: str,
			account_id: str,
			ts_code: str
	) -> Optional[PositionSnapshot]:
		"""
		获取指定股票的最新持仓快照

		Args:
			user_id: 用户ID
			account_id: 账户ID
			ts_code: 股票代码

		Returns:
			最新的持仓快照，如果没有则返回None
		"""
		query = select(PositionSnapshot).where(
			and_(
				PositionSnapshot.user_id == user_id,
				PositionSnapshot.account_id == account_id,
				PositionSnapshot.ts_code == ts_code
			)
		).order_by(PositionSnapshot.snapshot_date.desc()).limit(1)
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def create_daily_snapshot (
			self,
			user_id: str,
			account_id: str,
			ts_code: str,
			snapshot_date: date,
			volume: int,
			cost_price: float,
			market_value: float,
			last_price: float,
			pnl: float,
			pnl_rate: float
	) -> PositionSnapshot:
		"""
		创建每日持仓快照

		Args:
			user_id: 用户ID
			account_id: 账户ID
			ts_code: 股票代码
			snapshot_date: 快照日期
			volume: 持仓量
			cost_price: 成本价
			market_value: 持仓市值
			last_price: 最新价
			pnl: 持仓盈亏
			pnl_rate: 持仓盈亏率

		Returns:
			创建的持仓快照记录
		"""
		snapshot_data = {
			'user_id': user_id,
			'account_id': account_id,
			'ts_code': ts_code,
			'snapshot_date': snapshot_date,
			'volume': volume,
			'cost_price': cost_price,
			'market_value': market_value,
			'last_price': last_price,
			'pnl': pnl,
			'pnl_rate': pnl_rate,
			'created_at': datetime.now()
		}

		return await self.create(snapshot_data)

	async def batch_create_snapshots (
			self,
			snapshots_data: List[Dict[str, Any]]
	) -> List[PositionSnapshot]:
		"""
		批量创建持仓快照

		Args:
			snapshots_data: 快照数据列表

		Returns:
			创建的持仓快照记录列表
		"""
		# 添加创建时间
		for data in snapshots_data:
			if 'created_at' not in data:
				data['created_at'] = datetime.now()

		return await self.batch_create(snapshots_data)

	async def get_position_history (
			self,
			user_id: str,
			account_id: str,
			ts_code: str,
			days: int = 30
	) -> List[PositionSnapshot]:
		"""
		获取指定股票的持仓历史

		Args:
			user_id: 用户ID
			account_id: 账户ID
			ts_code: 股票代码
			days: 查询天数

		Returns:
			持仓历史快照列表
		"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days)

		return await self.get_many(
			and_(
				PositionSnapshot.user_id == user_id,
				PositionSnapshot.account_id == account_id,
				PositionSnapshot.ts_code == ts_code,
				PositionSnapshot.snapshot_date >= start_date,
				PositionSnapshot.snapshot_date <= end_date
			),
			order_by=PositionSnapshot.snapshot_date.asc()
		)

	async def get_account_total_value_history (
			self,
			account_id: str,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""
		获取账户总资产历史

		Args:
			account_id: 账户ID
			days: 查询天数

		Returns:
			每日总资产历史列表
		"""
		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days)

		# 使用原始SQL查询以提高性能
		query = select(
			PositionSnapshot.snapshot_date,
			func.sum(PositionSnapshot.market_value).label('total_value'),
			func.count(PositionSnapshot.ts_code).label('position_count')
		).where(
			and_(
				PositionSnapshot.account_id == account_id,
				PositionSnapshot.snapshot_date >= start_date,
				PositionSnapshot.snapshot_date <= end_date
			)
		).group_by(
			PositionSnapshot.snapshot_date
		).order_by(
			PositionSnapshot.snapshot_date.desc()
		)

		result = await self.session.execute(query)
		rows = result.all()

		return [
			{
				'date': row[0],
				'total_value': float(row[1]) if row[1] else 0,
				'position_count': row[2]
			}
			for row in rows
		]

	async def cleanup_old_snapshots (
			self,
			retention_days: int = 365
	) -> int:
		"""
		清理超过保留期限的快照记录

		Args:
			retention_days: 保留天数

		Returns:
			删除的记录数
		"""
		cutoff_date = datetime.now().date() - timedelta(days=retention_days)

		# 查找需要删除的记录
		query = select(PositionSnapshot.id).where(
			PositionSnapshot.snapshot_date < cutoff_date
		)

		result = await self.session.execute(query)
		record_ids = [row[0] for row in result.all()]

		# 批量删除
		deleted_count = 0
		for record_id in record_ids:
			success = await self.delete(record_id, soft=False)
			if success:
				deleted_count += 1

		return deleted_count

	async def get_snapshot_statistics (
			self,
			account_id: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		获取快照统计信息

		Args:
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			快照统计信息
		"""
		# 统计总记录数
		total_query = select(func.count()).select_from(PositionSnapshot).where(
			and_(
				PositionSnapshot.account_id == account_id,
				PositionSnapshot.snapshot_date >= start_date,
				PositionSnapshot.snapshot_date <= end_date
			)
		)
		total_result = await self.session.execute(total_query)
		total_count = total_result.scalar() or 0

		# 统计股票种类数
		stock_count_query = select(
			func.count(func.distinct(PositionSnapshot.ts_code))
		).where(
			and_(
				PositionSnapshot.account_id == account_id,
				PositionSnapshot.snapshot_date >= start_date,
				PositionSnapshot.snapshot_date <= end_date
			)
		)

		stock_count_result = await self.session.execute(stock_count_query)
		stock_count = stock_count_result.scalar() or 0

		# 获取最大和最小总资产
		value_query = select(
			PositionSnapshot.snapshot_date,
			func.sum(PositionSnapshot.market_value).label('total_value')
		).where(
			and_(
				PositionSnapshot.account_id == account_id,
				PositionSnapshot.snapshot_date >= start_date,
				PositionSnapshot.snapshot_date <= end_date
			)
		).group_by(
			PositionSnapshot.snapshot_date
		).order_by(
			func.sum(PositionSnapshot.market_value).desc()
		)

		value_result = await self.session.execute(value_query)
		value_rows = value_result.all()

		max_value = float(value_rows[0][1]) if value_rows else 0
		min_value = float(value_rows[-1][1]) if value_rows else 0

		return {
			'account_id': account_id,
			'period_start': start_date,
			'period_end': end_date,
			'total_snapshots': total_count,
			'unique_stocks': stock_count,
			'max_total_value': max_value,
			'min_total_value': min_value,
			'value_range': max_value - min_value
		}