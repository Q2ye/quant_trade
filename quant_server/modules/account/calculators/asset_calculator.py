# quant_server/modules/events/calculators/asset_calculator.py
"""
资产计算器 - 计算账户资产相关指标

职责：
1. 计算账户总资产
2. 计算持仓市值
3. 计算现金余额
4. 计算资产变化率
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ....modules.account.models import (
	AssetBreakdown,
	AssetHistory,
)
from ....shared.database.repositories import (
	AccountRepository,
	PositionRepository,
	TradeRepository,
	OrderRepository,
)


class AssetCalculator:
	"""资产计算器"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化资产计算器

		Args:
			session: 数据库会话
		"""
		self.session = session
		self.account_repo = AccountRepository(session)
		self.position_repo = PositionRepository(session)
		self.trade_repo = TradeRepository(session)
		self.order_repo = OrderRepository(session)

	async def calculate_total_asset (self, account_id: str, as_of_date: Optional[date] = None) -> Decimal:
		"""
		计算账户总资产

		Args:
			account_id: 账户ID
			as_of_date: 截止日期，None表示当前

		Returns:
			Decimal: 总资产金额
		"""
		# 获取账户信息
		account = await self.account_repo.get(account_id)
		if not account:
			raise ValueError(f"账户不存在: {account_id}")

		if as_of_date:
			# 历史计算：需要获取指定日期的持仓和现金
			# 这里简化处理，实际需要根据历史快照计算
			positions = await self.position_repo.get_account_positions(account_id)
			market_value = sum(
				pos.volume * pos.last_price
				for pos in positions
				if pos.volume > 0 and pos.last_price
			)

			# 获取历史现金（需要现金流水表，这里简化）
			# cash_history = await self.get_cash_history(account_id, as_of_date)
			# total_asset = cash_history + market_value

			# 简化：使用账户当前现金（实际项目需要更精确的历史数据）
			total_asset = account.available_balance + market_value
		else:
			# 当前计算：使用账户实时数据
			total_asset = account.total_balance

		return Decimal(str(total_asset))

	async def calculate_market_value (self, account_id: str) -> Decimal:
		"""
		计算持仓市值

		Args:
			account_id: 账户ID

		Returns:
			Decimal: 持仓市值
		"""
		positions = await self.position_repo.get_account_positions(account_id)

		total_market_value = Decimal('0')
		for position in positions:
			if position.volume > 0 and position.last_price:
				position_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))
				total_market_value += position_value

		return total_market_value

	async def calculate_cash_breakdown (self, account_id: str) -> Dict[str, Decimal]:
		"""
		计算现金构成

		Args:
			account_id: 账户ID

		Returns:
			Dict: 现金构成详情
		"""
		account = await self.account_repo.get(account_id)
		if not account:
			raise ValueError(f"账户不存在: {account_id}")

		return {
			"total_balance": Decimal(str(account.total_balance)),
			"available_balance": Decimal(str(account.available_balance)),
			"frozen_balance": Decimal(str(account.frozen_balance)),
			"margin_balance": Decimal(str(account.total_balance - account.available_balance - account.frozen_balance))
		}

	async def calculate_asset_allocation (self, account_id: str) -> List[AssetBreakdown]:
		"""
		计算资产配置详情

		Args:
			account_id: 账户ID

		Returns:
			List[AssetBreakdown]: 资产配置列表
		"""
		account = await self.account_repo.get(account_id)
		positions = await self.position_repo.get_account_positions(account_id)

		# 计算持仓市值
		position_values = []
		for position in positions:
			if position.volume > 0 and position.last_price:
				market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))
				position_values.append({
					"ts_code": position.ts_code,
					"market_value": market_value,
					"weight": market_value / Decimal(
						str(account.total_balance)) if account.total_balance > 0 else Decimal('0')
				})

		# 计算现金占比
		cash_value = Decimal(str(account.available_balance))
		cash_weight = cash_value / Decimal(str(account.total_balance)) if account.total_balance > 0 else Decimal('0')

		# 构建资产配置
		allocation = [
			AssetBreakdown(
				asset_type="cash",
				asset_name="现金",
				market_value=cash_value,
				weight=cash_weight,
				cost_basis=cash_value,
				pnl=Decimal('0')
			)
		]

		# 持仓部分
		for pos_value in position_values:
			position = next(p for p in positions if p.ts_code == pos_value["ts_code"])

			allocation.append(AssetBreakdown(
				asset_type="stock",
				asset_name=position.ts_code,
				market_value=pos_value["market_value"],
				weight=pos_value["weight"],
				cost_basis=Decimal(str(position.cost_price)) * Decimal(str(position.volume)),
				pnl=Decimal(str(position.pnl))
			))

		return allocation

	@staticmethod
	async def calculate_asset_history (
			_account_id: int,
			_start_date: date,
			_end_date: date
	) -> List[AssetHistory]:
		"""
		计算资产历史

		Args:
			_account_id: 账户ID
			_start_date: 开始日期
			_end_date: 结束日期

		Returns:
			List[AssetHistory]: 资产历史记录
		"""
		# 获取账户每日绩效快照
		# 这里需要从AccountDailyPerformance表获取数据
		# 简化实现：返回空列表，实际需要根据业务逻辑实现

		# TODO: 实现从AccountDailyPerformance表查询历史数据
		# performance_records = await self.account_repo.get_performance_history(
		#     account_id, start_date, end_date
		# )

		# 转换为AssetHistory对象
		return []

	@staticmethod
	async def calculate_asset_growth_rate (
			_account_id: int,
			_start_date: date,
			_end_date: date
	) -> Dict[str, Decimal]:
		"""
		计算资产增长率

		Args:
			_account_id: 账户ID
			_start_date: 开始日期
			_end_date: 结束日期

		Returns:
			Dict: 增长率指标
		"""
		# 获取期初和期末资产
		# 简化实现，实际需要从历史快照获取

		# start_asset = await self.get_asset_at_date(account_id, start_date)
		# end_asset = await self.get_asset_at_date(account_id, end_date)

		# if not start_asset or not end_asset:
		#     return {}

		# total_return = (end_asset - start_asset) / start_asset
		# annualized_return = self._annualize_return(total_return, start_date, end_date)

		return {
			"total_return": Decimal('0'),  # total_return
			"annualized_return": Decimal('0'),  # annualized_return
			"cagr": Decimal('0'),  # 复合年增长率
		}

	@staticmethod
	def _annualize_return (total_return: Decimal, start_date: date, end_date: date) -> Decimal:
		"""
		年化收益率计算

		Args:
			total_return: 总收益率
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			Decimal: 年化收益率
		"""
		days_diff = (end_date - start_date).days
		years = Decimal(str(days_diff)) / Decimal('365')

		if years <= 0:
			return Decimal('0')

		# 年化公式: (1 + total_return)^(1/years) - 1
		try:
			annualized = (Decimal('1') + total_return) ** (Decimal('1') / years) - Decimal('1')
		except (ValueError, ZeroDivisionError):
			annualized = Decimal('0')

		return annualized