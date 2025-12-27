# -*- coding: utf-8 -*-
"""
持仓数据仓库
提供用户持仓数据的统一访问接口
位置：shared/database/repositories/position_repo.py
"""

from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from .base import BaseRepository
from quant_server.shared.database.models.business_models import Position


class PositionRepository:
	"""持仓数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.base_repo = BaseRepository(session, Position)

	# ==================== 基础CRUD操作 ====================

	async def create (self, data: Dict[str, Any]) -> Position:
		"""创建持仓记录"""
		return await self.base_repo.create(data)

	async def get (self, id: int) -> Optional[Position]:
		"""根据ID获取持仓记录"""
		return await self.base_repo.get(id)

	async def update (self, id: int, data: Dict[str, Any]) -> Optional[Position]:
		"""更新持仓记录"""
		return await self.base_repo.update(id, data)

	async def delete (self, id: int, soft: bool = True) -> bool:
		"""删除持仓记录"""
		return await self.base_repo.delete(id, soft)

	async def get_one (self, *filters) -> Optional[Position]:
		"""根据条件获取单个持仓记录"""
		return await self.base_repo.get_one(*filters)

	async def get_many (
			self,
			*filters,
			skip: int = 0,
			limit: int = 100,
			order_by: str = None
	) -> List[Position]:
		"""根据条件获取多个持仓记录"""
		return await self.base_repo.get_many(*filters, skip=skip, limit=limit, order_by=order_by)

	async def count (self, *filters) -> int:
		"""统计持仓记录数"""
		return await self.base_repo.count(*filters)

	# ==================== 业务查询方法 ====================

	async def get_user_position (
			self,
			user_id: int,
			ts_code: str
	) -> Optional[Position]:
		"""获取用户特定股票的持仓"""
		return await self.get_one(
			and_(
				Position.user_id == user_id,
				Position.ts_code == ts_code
			)
		)

	async def get_user_positions (
			self,
			user_id: int,
			include_zero: bool = False
	) -> List[Position]:
		"""获取用户的所有持仓"""
		filters = [Position.user_id == user_id]

		if not include_zero:
			filters.append(Position.volume > 0)

		return await self.get_many(*filters, order_by=Position.ts_code.asc())

	async def get_stock_holders (
			self,
			ts_code: str,
			min_volume: int = 0
	) -> List[Position]:
		"""获取持有特定股票的所有用户"""
		filters = [
			Position.ts_code == ts_code,
			Position.volume >= min_volume
		]

		return await self.get_many(*filters, order_by=Position.volume.desc())

	async def get_position_summary (
			self,
			user_id: int
	) -> Dict[str, Any]:
		"""获取用户持仓汇总"""
		positions = await self.get_user_positions(user_id, include_zero=False)

		if not positions:
			return {
				'user_id': user_id,
				'total_positions': 0,
				'total_market_value': 0,
				'total_volume': 0,
				'avg_cost_price': 0
			}

		total_market_value = sum(float(p.market_value) for p in positions)
		total_volume = sum(p.volume for p in positions)
		total_cost = sum(float(p.cost_price) * p.volume for p in positions)

		avg_cost_price = total_cost / total_volume if total_volume > 0 else 0

		return {
			'user_id': user_id,
			'total_positions': len(positions),
			'total_market_value': total_market_value,
			'total_volume': total_volume,
			'avg_cost_price': avg_cost_price,
			'positions': [
				{
					'ts_code': p.ts_code,
					'volume': p.volume,
					'available_volume': p.available_volume,
					'cost_price': float(p.cost_price),
					'market_value': float(p.market_value),
					'last_update': p.last_update.isoformat() if p.last_update else None
				}
				for p in positions
			]
		}

	async def get_top_positions (
			self,
			user_id: int,
			top_n: int = 10,
			sort_by: str = 'market_value'  # 'market_value', 'volume', 'pnl'
	) -> List[Dict[str, Any]]:
		"""获取用户持仓排名（按市值、数量等）"""
		positions = await self.get_user_positions(user_id, include_zero=False)

		if not positions:
			return []

		# 计算持仓盈亏（需要最新价格，这里只是示例）
		# 实际中需要从行情数据获取最新价格
		for position in positions:
			# 这里只是示例，实际需要查询最新价格
			position.current_price = float(position.cost_price)  # 假设当前价格等于成本价
			position.pnl = (position.current_price - float(position.cost_price)) * position.volume

		# 排序
		if sort_by == 'market_value':
			positions.sort(key=lambda p: float(p.market_value), reverse=True)
		elif sort_by == 'volume':
			positions.sort(key=lambda p: p.volume, reverse=True)
		elif sort_by == 'pnl':
			positions.sort(key=lambda p: p.pnl, reverse=True)

		# 只返回前N个
		top_positions = positions[:top_n]

		return [
			{
				'rank': idx + 1,
				'ts_code': p.ts_code,
				'volume': p.volume,
				'available_volume': p.available_volume,
				'cost_price': float(p.cost_price),
				'market_value': float(p.market_value),
				'current_price': p.current_price,
				'pnl': p.pnl,
				'pnl_percent': (p.current_price - float(p.cost_price)) / float(p.cost_price) * 100
				if float(p.cost_price) > 0 else 0,
				'last_update': p.last_update.isoformat() if p.last_update else None
			}
			for idx, p in enumerate(top_positions)
		]

	async def get_sector_distribution (
			self,
			user_id: int
	) -> Dict[str, float]:
		"""获取用户持仓的行业分布（需要关联股票基础信息）"""
		# 这里只是示例，实际需要关联stock_basic表获取行业信息
		positions = await self.get_user_positions(user_id, include_zero=False)

		if not positions:
			return {}

		# 模拟行业分布（实际需要查询股票行业信息）
		sector_distribution = {}
		total_market_value = sum(float(p.market_value) for p in positions)

		if total_market_value > 0:
			for position in positions:
				# 这里只是示例，实际需要查询行业信息
				sector = "未知行业"  # 实际应该从股票基础信息获取

				if sector not in sector_distribution:
					sector_distribution[sector] = 0

				sector_distribution[sector] += float(position.market_value) / total_market_value * 100

		return sector_distribution

	async def update_position (
			self,
			user_id: int,
			ts_code: str,
			volume_change: int,
			price: float,
			trade_type: str  # 'buy' or 'sell'
	) -> Optional[Position]:
		"""更新持仓（买入或卖出）"""
		position = await self.get_user_position(user_id, ts_code)

		if trade_type == 'buy':
			if position:
				# 更新现有持仓
				new_volume = position.volume + volume_change
				new_available = position.available_volume + volume_change

				# 计算新的成本价（加权平均）
				old_cost = float(position.cost_price) * position.volume
				new_cost = price * volume_change
				total_cost = old_cost + new_cost
				new_cost_price = total_cost / new_volume if new_volume > 0 else 0

				update_data = {
					'volume': new_volume,
					'available_volume': new_available,
					'cost_price': new_cost_price,
					'last_update': datetime.now()
				}

				return await self.update(position.id, update_data)
			else:
				# 创建新持仓
				position_data = {
					'user_id': user_id,
					'ts_code': ts_code,
					'volume': volume_change,
					'available_volume': volume_change,
					'cost_price': price,
					'market_value': price * volume_change,
					'last_update': datetime.now()
				}

				return await self.create(position_data)

		elif trade_type == 'sell':
			if not position or position.available_volume < volume_change:
				# 持仓不足
				return None

			new_volume = position.volume - volume_change
			new_available = position.available_volume - volume_change

			if new_volume <= 0:
				# 清仓，删除持仓记录
				await self.delete(position.id, soft=False)
				return None
			else:
				# 部分卖出，成本价不变
				update_data = {
					'volume': new_volume,
					'available_volume': new_available,
					'last_update': datetime.now()
				}

				return await self.update(position.id, update_data)

		return None

	async def update_market_value (
			self,
			user_id: int,
			ts_code: str,
			current_price: float
	) -> Optional[Position]:
		"""更新持仓市值"""
		position = await self.get_user_position(user_id, ts_code)

		if not position:
			return None

		market_value = current_price * position.volume

		update_data = {
			'market_value': market_value,
			'last_update': datetime.now()
		}

		return await self.update(position.id, update_data)

	async def batch_update_market_values (
			self,
			updates: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""批量更新持仓市值"""
		success_count = 0
		failed_count = 0

		for update in updates:
			user_id = update.get('user_id')
			ts_code = update.get('ts_code')
			current_price = update.get('current_price')

			if not user_id or not ts_code or current_price is None:
				failed_count += 1
				continue

			try:
				result = await self.update_market_value(user_id, ts_code, current_price)
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
			max_value: float = None
	) -> List[Position]:
		"""根据市值范围获取持仓"""
		filters = [Position.market_value >= min_value]

		if max_value is not None:
			filters.append(Position.market_value <= max_value)

		return await self.get_many(*filters, order_by=Position.market_value.desc())

	async def get_recently_updated (
			self,
			hours: int = 24
	) -> List[Position]:
		"""获取最近更新的持仓"""
		cutoff_time = datetime.now() - timedelta(hours=hours)

		return await self.get_many(
			Position.last_update >= cutoff_time,
			order_by=Position.last_update.desc()
		)

	async def get_position_history (
			self,
			user_id: int,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""获取持仓历史（需要关联交易记录）"""
		# 这里只是示例，实际需要关联trade表获取历史
		# 返回最近N天的持仓变化

		end_date = datetime.now().date()
		start_date = end_date - timedelta(days=days - 1)

		# 模拟返回数据
		return [
			{
				'date': start_date + timedelta(days=i),
				'total_value': 1000000 + i * 10000,  # 模拟数据
				'position_count': 5 + (i % 3)  # 模拟数据
			}
			for i in range(days)
		]

	async def get_low_available_positions (
			self,
			threshold: float = 0.1  # 可用比例阈值
	) -> List[Position]:
		"""获取可用比例较低的持仓（可能被冻结）"""
		query = select(Position).where(
			and_(
				Position.volume > 0,
				Position.available_volume < Position.volume * threshold
			)
		).order_by(
			(Position.available_volume / Position.volume).asc()
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_position_statistics (self) -> Dict[str, Any]:
		"""获取持仓数据统计"""
		# 统计总持仓记录数
		total_count = await self.count()

		# 统计有持仓的用户数
		user_count = await self.session.execute(
			select(func.count(func.distinct(Position.user_id)))
		)
		user_count_value = user_count.scalar() or 0

		# 统计总市值
		total_market_value = await self.session.execute(
			select(func.sum(Position.market_value))
		)
		total_market_value_value = total_market_value.scalar() or 0

		# 统计总持仓数量
		total_volume = await self.session.execute(
			select(func.sum(Position.volume))
		)
		total_volume_value = total_volume.scalar() or 0

		# 统计持仓股票种类数
		stock_count = await self.session.execute(
			select(func.count(func.distinct(Position.ts_code)))
		)
		stock_count_value = stock_count.scalar() or 0

		# 获取持仓最多的用户
		top_users = await self.session.execute(
			select(
				Position.user_id,
				func.sum(Position.market_value).label('total_value')
			).group_by(
				Position.user_id
			).order_by(
				func.sum(Position.market_value).desc()
			).limit(5)
		)

		top_users_list = [
			{'user_id': row[0], 'total_value': float(row[1]) if row[1] else 0}
			for row in top_users.all()
		]

		# 获取最受欢迎的股票
		popular_stocks = await self.session.execute(
			select(
				Position.ts_code,
				func.count(Position.user_id).label('holder_count')
			).group_by(
				Position.ts_code
			).order_by(
				func.count(Position.user_id).desc()
			).limit(10)
		)

		popular_stocks_list = [
			{'ts_code': row[0], 'holder_count': row[1]}
			for row in popular_stocks.all()
		]

		return {
			'total_positions': total_count,
			'unique_users': user_count_value,
			'unique_stocks': stock_count_value,
			'total_market_value': float(total_market_value_value),
			'total_volume': total_volume_value,
			'avg_position_value': float(total_market_value_value) / user_count_value
			if user_count_value > 0 else 0,
			'top_users': top_users_list,
			'popular_stocks': popular_stocks_list
		}

	async def batch_create (
			self,
			data_list: List[Dict[str, Any]]
	) -> List[Position]:
		"""批量创建持仓记录"""
		return await self.base_repo.batch_create(data_list)

	async def batch_upsert (
			self,
			data_list: List[Dict[str, Any]],
			match_fields: List[str] = ['user_id', 'ts_code']
	) -> List[Position]:
		"""批量插入或更新持仓记录"""
		return await self.base_repo.batch_upsert(data_list, match_fields)

	async def clear_user_positions (self, user_id: int) -> int:
		"""清空用户所有持仓"""
		positions = await self.get_user_positions(user_id, include_zero=True)

		cleared = 0
		for position in positions:
			success = await self.delete(position.id, soft=False)
			if success:
				cleared += 1

		return cleared