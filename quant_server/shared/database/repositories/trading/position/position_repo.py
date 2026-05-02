# -*- coding: utf-8 -*-
"""
持仓数据仓库
提供用户持仓数据的统一访问接口
位置：shared/database/repositories/trading/position/position_repo.py
"""

import logging
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.models.business_models import Position
from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError

logger = logging.getLogger(__name__)


class PositionRepository(BaseRepository[Position]):
	"""持仓数据Repository - 纯数据访问"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, Position)

	async def get_user_position (
			self,
			user_id: str,
			account_id: str,
			ts_code: str
	) -> Optional[Position]:
		"""获取用户特定股票的持仓"""
		# 使用构建查询的方式获取记录
		query = self.build_query()
		query = query.where(
			and_(
				Position.user_id == user_id,
				Position.account_id == account_id,
				Position.ts_code == ts_code
			)
		)
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_user_positions (
			self,
			user_id: str,
			account_id: Optional[str] = None,
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
			account_id: str,
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

	async def get_current_positions (self, account_id: str) -> List[Position]:
		"""获取账户的当前持仓"""
		return await self.get_account_positions(account_id, include_zero=False)

	async def get_positions_by_date (self, account_id: str, trading_date: date) -> List[Position]:
		"""
		根据日期获取持仓记录

		Args:
			account_id: 账户ID
			trading_date: 交易日

		Returns:
			持仓记录列表
		"""
		# 这里简化处理，实际需要根据日期获取持仓
		# 暂时返回当前持仓
		# 预留参数，后续实现时会使用
		_ = trading_date
		return await self.get_account_positions(account_id, include_zero=False)

	async def create_reconciliation_record (self, recon_data: Dict[str, Any]) -> Any:
		"""
		创建持仓对账记录

		Args:
			recon_data: 对账数据

		Returns:
			创建的对账记录
		"""
		try:
			# 这里简化处理，实际需要创建对账记录
			class MockRecord:
				def __init__ (self, id):
					self.id = id

			return MockRecord(
				id=f"position_recon_{recon_data['account_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

		except Exception as e:
			raise RepositoryError(f"创建持仓对账记录失败: {str(e)}")

	async def update_position (self, account_id: str, security_id: str, position_data: Dict[str, Any]) -> Optional[
		Position]:
		"""
		更新持仓

		Args:
			account_id: 账户ID
			security_id: 证券代码
			position_data: 持仓数据

		Returns:
			更新后的持仓记录
		"""
		try:
			# 查找持仓
			query = self.build_query()
			query = query.where(
				and_(
					Position.account_id == account_id,
					Position.ts_code == security_id
				)
			)
			result = await self.session.execute(query)
			position = result.scalar_one_or_none()

			if not position:
				# 创建新持仓
				position_data['account_id'] = account_id
				position_data['ts_code'] = security_id
				position_data['created_at'] = datetime.now()
				position_data['updated_at'] = datetime.now()
				return await self.create(position_data)
			else:
				# 更新现有持仓
				position_data['updated_at'] = datetime.now()
				return await self.update(position.id, position_data)

		except Exception as e:
			raise RepositoryError(f"更新持仓失败: {str(e)}")

	async def get_stock_holders (
			self,
			ts_code: str,
			min_volume: int = 0,
			account_id: Optional[str] = None
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
			position_id: str,
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
			position_id: str,
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
			position_id: str,
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
			position_id: str,
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
			position_id: str,
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
			except RepositoryError:
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
			account_id: Optional[str] = None
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
			account_id: Optional[str] = None
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
			account_id: Optional[str] = None
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
			account_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""获取持仓数据统计"""
		filters = []
		if account_id:
			filters.append(Position.account_id == account_id)

		# 统计总持仓记录数
		count_query = select(func.count()).select_from(Position)
		if filters:
			count_query = count_query.where(and_(*filters))
		total_count_result = await self.session.execute(count_query)
		total_count = total_count_result.scalar() or 0

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
			account_id: str,
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

	async def get_positions_by_ts_code (
			self,
			ts_code: str,
			min_volume: int = 0
	) -> List[Position]:
		"""
		根据股票代码获取持仓记录

		Args:
			ts_code: 股票代码
			min_volume: 最小持仓量

		Returns:
			持仓记录列表
		"""
		try:
			query = select(Position).where(
				and_(
					Position.ts_code == ts_code,
					Position.volume >= min_volume
				)
			).order_by(Position.volume.desc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取股票持仓失败: {str(e)}")

	@staticmethod
	async def get_positions_by_industry (
			industry_code: str,
			account_id: Optional[str] = None
	) -> List[Position]:
		"""
		根据行业代码获取持仓记录

		Args:
			industry_code: 行业代码
			account_id: 账户ID筛选

		Returns:
			持仓记录列表
		"""
		try:
			# 这里需要关联股票基本信息表获取行业信息
			# 暂时返回空列表，实际实现需要关联查询
			# 预留参数，后续实现时会使用
			_ = industry_code
			_ = account_id
			return []
		except Exception as e:
			raise RepositoryError(f"获取行业持仓失败: {str(e)}")

	async def get_high_risk_positions (
			self,
			pnl_threshold: float = -0.1,
			account_id: Optional[str] = None
	) -> List[Position]:
		"""
		获取高风险持仓（高亏损）

		Args:
			pnl_threshold: 亏损率阈值
			account_id: 账户ID筛选

		Returns:
			高风险持仓列表
		"""
		try:
			filters = [Position.pnl_rate <= pnl_threshold, Position.volume > 0]

			if account_id:
				filters.append(Position.account_id == account_id)

			query = select(Position).where(
				and_(*filters)
			).order_by(Position.pnl_rate.asc())

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取高风险持仓失败: {str(e)}")

	async def get_concentrated_positions (
			self,
			concentration_threshold: float = 0.1,
			account_id: Optional[str] = None
	) -> List[Position]:
		"""
		获取集中度较高的持仓

		Args:
			concentration_threshold: 集中度阈值
			account_id: 账户ID筛选

		Returns:
			集中度较高持仓列表
		"""
		try:
			# 计算每个账户的总市值
			total_value_subquery = select(
				Position.account_id,
				func.sum(Position.market_value).label('total_account_value')
			).where(Position.volume > 0)

			if account_id:
				total_value_subquery = total_value_subquery.where(Position.account_id == account_id)

			total_value_subquery = total_value_subquery.group_by(Position.account_id).subquery()

			# 查询集中度较高地持仓
			query = select(Position).join(
				total_value_subquery,  # type: ignore
				Position.account_id == total_value_subquery.c.account_id
			).where(
				and_(
					Position.volume > 0,
					Position.market_value / total_value_subquery.c.total_account_value >= concentration_threshold
				)
			).order_by(
				(Position.market_value / total_value_subquery.c.total_account_value).desc()
			)

			result = await self.session.execute(query)
			return result.scalars().all()
		except Exception as e:
			raise RepositoryError(f"获取集中度持仓失败: {str(e)}")

	async def batch_update_positions (
			self,
			updates: List[Dict[str, Any]]
	) -> Dict[str, int]:
		"""
		批量更新持仓记录

		Args:
			updates: 更新数据列表，每个元素包含position_id和更新字段

		Returns:
			更新结果统计
		"""
		success_count = 0
		failed_count = 0

		for update_data in updates:
			position_id = update_data.get('id')
			if not position_id:
				failed_count += 1
				continue

			try:
				update_data['last_update'] = datetime.now()
				result = await self.update(position_id, update_data)
				if result:
					success_count += 1
				else:
					failed_count += 1
			except RepositoryError as e:
				logger.warning("批量更新持仓失败 position_id=%s: %s", position_id, e)
				failed_count += 1

		return {
			'success': success_count,
			'failed': failed_count,
			'total': len(updates)
		}

	@staticmethod
	async def get_position_trend (
			account_id: str,
			ts_code: str,
			days: int = 30
	) -> List[Dict[str, Any]]:
		"""
		获取持仓趋势数据

		Args:
			account_id: 账户ID
			ts_code: 股票代码
			days: 天数

		Returns:
			持仓趋势数据列表
		"""
		try:
			# 这里需要关联持仓快照表获取历史数据
			# 暂时返回模拟数据
			# 预留参数，后续实现时会使用
			_ = account_id
			_ = ts_code
			return [
				{
					'date': (datetime.now() - timedelta(days=i)).date(),
					'volume': 1000 + i * 100,
					'market_value': 10000 + i * 1000
				}
				for i in range(days, 0, -1)
			]
		except Exception as e:
			raise RepositoryError(f"获取持仓趋势失败: {str(e)}")

	async def export_positions (
			self,
			account_id: Optional[str] = None,
			format_type: str = 'csv'
	) -> str:
		"""
		导出持仓数据

		Args:
			account_id: 账户ID筛选
			format_type: 导出格式（csv/json）

		Returns:
			导出文件路径或内容
		"""
		try:
			# 获取持仓数据，后续实现时会使用
			_ = await self.get_account_positions(account_id) if account_id else await self.get_all()

			# 这里简化处理，实际需要生成输出文件
			return f"positions_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
		except Exception as e:
			raise RepositoryError(f"导出持仓数据失败: {str(e)}")

	@staticmethod
	async def validate_position_data (position_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		验证持仓数据有效性

		Args:
			position_data: 持仓数据

		Returns:
			验证结果
		"""
		try:
			# 基本数据验证
			if 'volume' in position_data and position_data['volume'] < 0:
				return {'valid': False, 'error': '持仓量不能为负数'}

			if 'available_volume' in position_data and position_data['available_volume'] < 0:
				return {'valid': False, 'error': '可用持仓量不能为负数'}

			if 'frozen_volume' in position_data and position_data['frozen_volume'] < 0:
				return {'valid': False, 'error': '冻结持仓量不能为负数'}

			# 验证数量一致性
			if all(key in position_data for key in ['volume', 'available_volume', 'frozen_volume']):
				if position_data['volume'] != position_data['available_volume'] + position_data['frozen_volume']:
					return {'valid': False, 'error': '总持仓量不等于可用量加冻结量'}

			return {'valid': True, 'error': None}
		except Exception as e:
			return {'valid': False, 'error': f"数据验证失败: {str(e)}"}