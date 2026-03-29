# -*- coding: utf-8 -*-
"""
持仓数据仓库
提供用户持仓数据的统一访问接口
位置：shared/database/repositories/trading/position/position_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError
from quant_server.shared.database.models.business_models import Position


class PositionRepository(BaseRepository[Position]):
	"""持仓数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, Position)

	async def get_user_position (
			self,
			user_id: int,
			account_id: int,
			ts_code: str
	) -> Optional[Position]:
		"""获取用户特定股票的持仓"""
		return await self.get_one(
			and_(
				Position.user_id == user_id,
				Position.account_id == account_id,
				Position.ts_code == ts_code
			)
		)

	async def get_user_positions (
			self,
			user_id: int,
			account_id: Optional[int] = None,
			include_zero: bool = False
	) -> List[Position]:
		"""获取用户的所有持仓"""
		try:
			query = select(Position).where(Position.user_id == user_id)

			if account_id:
				query = query.where(Position.account_id == account_id)

			if not include_zero:
				query = query.where(Position.volume > 0)

			query = query.order_by(Position.ts_code.asc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取用户持仓失败: {str(e)}")

	async def get_account_positions (
			self,
			account_id: int,
			include_zero: bool = False
	) -> List[Position]:
		"""获取账户的所有持仓"""
		try:
			query = select(Position).where(Position.account_id == account_id)

			if not include_zero:
				query = query.where(Position.volume > 0)

			query = query.order_by(Position.ts_code.asc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取账户持仓失败: {str(e)}")

	async def get_stock_holders (
			self,
			ts_code: str,
			min_volume: int = 0,
			account_id: Optional[int] = None
	) -> List[Position]:
		"""获取持有特定股票的所有用户"""
		try:
			query = select(Position).where(
				Position.ts_code == ts_code,
				Position.volume >= min_volume
			)

			if account_id:
				query = query.where(Position.account_id == account_id)

			query = query.order_by(Position.volume.desc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取持股者失败: {str(e)}")

	async def update_position_volume (
			self,
			position_id: int,
			volume_change: int,
			available_change: int = 0,
			frozen_change: int = 0
	) -> Optional[Position]:
		"""
		更新持仓数量

		Args:
			position_id: 持仓ID
			volume_change: 总数量变化
			available_change: 可用数量变化
			frozen_change: 冻结数量变化

		Returns:
			更新后的持仓记录
		"""
		# 先获取当前持仓
		position = await self.get(position_id)
		if not position:
			return None

		update_data = {
			'volume': position.volume + volume_change,
			'available_volume': position.available_volume + available_change,
			'frozen_volume': position.frozen_volume + frozen_change,
			'last_update': datetime.now()
		}

		# 验证数量有效性
		if update_data['volume'] < 0 or update_data['available_volume'] < 0:
			return None

		return await self.update(position_id, update_data)

	async def update_position_cost (
			self,
			position_id: int,
			new_cost_price: float
	) -> Optional[Position]:
		"""
		更新持仓成本价

		Args:
			position_id: 持仓ID
			new_cost_price: 新的成本价

		Returns:
			更新后的持仓记录
		"""
		update_data = {
			'cost_price': new_cost_price,
			'last_update': datetime.now()
		}

		return await self.update(position_id, update_data)

	async def update_position_market_value (
			self,
			position_id: int,
			last_price: float
	) -> Optional[Position]:
		"""
		更新持仓市值和盈亏

		Args:
			position_id: 持仓ID
			last_price: 最新价格

		Returns:
			更新后的持仓记录
		"""
		position = await self.get(position_id)
		if not position:
			return None

		market_value = last_price * position.volume
		pnl = (last_price - float(position.cost_price)) * position.volume
		pnl_rate = (last_price - float(position.cost_price)) / float(position.cost_price) * 100 if float(
			position.cost_price) > 0 else 0

		update_data = {
			'market_value': market_value,
			'last_price': last_price,
			'pnl': pnl,
			'pnl_rate': pnl_rate,
			'last_update': datetime.now()
		}

		return await self.update(position_id, update_data)

	async def freeze_position (
			self,
			position_id: int,
			freeze_volume: int
	) -> Optional[Position]:
		"""
		冻结持仓

		Args:
			position_id: 持仓ID
			freeze_volume: 冻结数量

		Returns:
			更新后的持仓记录
		"""
		position = await self.get(position_id)
		if not position or position.available_volume < freeze_volume:
			return None

		update_data = {
			'available_volume': position.available_volume - freeze_volume,
			'frozen_volume': position.frozen_volume + freeze_volume,
			'last_update': datetime.now()
		}

		return await self.update(position_id, update_data)

	async def unfreeze_position (
			self,
			position_id: int,
			unfreeze_volume: int
	) -> Optional[Position]:
		"""
		解冻持仓

		Args:
			position_id: 持仓ID
			unfreeze_volume: 解冻数量

		Returns:
			更新后的持仓记录
		"""
		position = await self.get(position_id)
		if not position or position.frozen_volume < unfreeze_volume:
			return None

		update_data = {
			'available_volume': position.available_volume + unfreeze_volume,
			'frozen_volume': position.frozen_volume - unfreeze_volume,
			'last_update': datetime.now()
		}

		return await self.update(position_id, update_data)

	async def batch_update_market_values (
			self,
			updates: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""
		批量更新持仓市值

		Args:
			updates: 更新数据列表，每个元素包含position_id和last_price

		Returns:
			更新结果统计
		"""
		success_count = 0
		failed_count = 0

		for update in updates:
			position_id = update.get('position_id')
			last_price = update.get('last_price')

			if not position_id or last_price is None:
				failed_count += 1
				continue

			try:
				result = await self.update_position_market_value(position_id, last_price)
				if result:
					success_count += 1
				else:
					failed_count += 1
			except Exception:
				failed_count += 1

		return {
			'success': success_count,
			'failed': failed_count,
			'total': len(updates)
		}

	async def get_positions_by_value_range (
			self,
			min_value: float = 0,
			max_value: float = None,
			account_id: Optional[int] = None
	) -> List[Position]:
		"""根据市值范围获取持仓"""
		try:
			query = select(Position).where(Position.market_value >= min_value)

			if max_value is not None:
				query = query.where(Position.market_value <= max_value)

			if account_id:
				query = query.where(Position.account_id == account_id)

			query = query.order_by(Position.market_value.desc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取市值范围持仓失败: {str(e)}")

	async def get_recently_updated (
			self,
			hours: int = 24,
			account_id: Optional[int] = None
	) -> List[Position]:
		"""获取最近更新的持仓"""
		try:
			cutoff_time = datetime.now() - timedelta(hours=hours)

			query = select(Position).where(Position.last_update >= cutoff_time)

			if account_id:
				query = query.where(Position.account_id == account_id)

			query = query.order_by(Position.last_update.desc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取最近更新持仓失败: {str(e)}")

	async def get_low_available_positions (
			self,
			threshold: float = 0.1,
			account_id: Optional[int] = None
	) -> List[Position]:
		"""
		获取可用比例较低的持仓（可能被冻结）

		Args:
			threshold: 可用比例阈值（0-1）
			account_id: 账户ID筛选

		Returns:
			可用比例较低的持仓列表
		"""
		filters = [
			Position.volume > 0,
			Position.available_volume < Position.volume * threshold
		]

		if account_id:
			filters.append(Position.account_id == account_id)

		query = select(Position).where(
			and_(*filters)
		).order_by(
			(Position.available_volume / Position.volume).asc()
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_position_statistics (
			self,
			account_id: Optional[int] = None
	) -> Dict[str, Any]:
		"""获取持仓数据统计"""
		filters = []
		if account_id:
			filters.append(Position.account_id == account_id)

		# 统计总持仓记录数
		total_count = await self.count(*filters)

		# 统计有持仓的用户数
		if account_id:
			user_count = 1  # 单个账户只有一个用户
		else:
			user_count_query = select(
				func.count(func.distinct(Position.user_id))
			)
			if filters:
				user_count_query = user_count_query.where(and_(*filters))

			user_count_result = await self.session.execute(user_count_query)
			user_count = user_count_result.scalar() or 0

		# 统计总市值
		total_value_query = select(func.sum(Position.market_value))
		if filters:
			total_value_query = total_value_query.where(and_(*filters))

		total_value_result = await self.session.execute(total_value_query)
		total_market_value = total_value_result.scalar() or 0

		# 统计总持仓数量
		total_volume_query = select(func.sum(Position.volume))
		if filters:
			total_volume_query = total_volume_query.where(and_(*filters))

		total_volume_result = await self.session.execute(total_volume_query)
		total_volume = total_volume_result.scalar() or 0

		# 统计持仓股票种类数
		stock_count_query = select(func.count(func.distinct(Position.ts_code)))
		if filters:
			stock_count_query = stock_count_query.where(and_(*filters))

		stock_count_result = await self.session.execute(stock_count_query)
		stock_count = stock_count_result.scalar() or 0

		# 获取持仓最多的股票
		top_stocks_query = select(
			Position.ts_code,
			func.sum(Position.market_value).label('total_value'),
			func.sum(Position.volume).label('total_volume')
		)

		if filters:
			top_stocks_query = top_stocks_query.where(and_(*filters))

		top_stocks_query = top_stocks_query.group_by(
			Position.ts_code
		).order_by(
			func.sum(Position.market_value).desc()
		).limit(10)

		top_stocks_result = await self.session.execute(top_stocks_query)
		top_stocks = [
			{
				'ts_code': row[0],
				'total_value': float(row[1]) if row[1] else 0,
				'total_volume': row[2] or 0
			}
			for row in top_stocks_result.all()
		]

		return {
			'total_positions': total_count,
			'unique_users': user_count,
			'unique_stocks': stock_count,
			'total_market_value': float(total_market_value),
			'total_volume': total_volume,
			'avg_position_value': float(total_market_value) / total_count if total_count > 0 else 0,
			'top_stocks': top_stocks
		}

	async def clear_account_positions (
			self,
			account_id: int,
			soft_delete: bool = False
	) -> int:
		"""
		清空账户所有持仓

		Args:
			account_id: 账户ID
			soft_delete: 是否软删除

		Returns:
			删除的持仓记录数
		"""
		positions = await self.get_account_positions(account_id, include_zero=True)

		cleared = 0
		for position in positions:
			success = await self.delete(position.id, soft=soft_delete)
			if success:
				cleared += 1

		return cleared