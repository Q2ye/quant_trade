# quant_server/modules/events/calculators/pnl_calculator.py
"""
盈亏计算器 - 计算账户盈亏相关指标

职责：
1. 计算持仓盈亏
2. 计算交易盈亏
3. 计算已实现/未实现盈亏
4. 计算盈亏分析
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from enum import Enum
from sqlalchemy.orm import Session

from quant_server.shared.database.repositories import (
	PositionRepository,
	TradeRepository,
	OrderRepository,
	AccountRepository,
)
from quant_server.modules.account.models import (
	PositionPnL,
	TradePnL,
	DailyPnLSummary,
	PnLAnalysis,
)


class PnLType(Enum):
	"""盈亏类型枚举"""
	REALIZED = "realized"  # 已实现盈亏
	UNREALIZED = "unrealized"  # 未实现盈亏
	TOTAL = "total"  # 总盈亏


class PnLCalculator:
	"""盈亏计算器"""

	def __init__ (self, session: Session):
		"""
		初始化盈亏计算器

		Args:
			session: 数据库会话
		"""
		self.session = session
		self.position_repo = PositionRepository(session)
		self.trade_repo = TradeRepository(session)
		self.order_repo = OrderRepository(session)
		self.account_repo = AccountRepository(session)

	async def calculate_position_pnl (self, account_id: int) -> List[PositionPnL]:
		"""
		计算持仓盈亏

		Args:
			account_id: 账户ID

		Returns:
			List[PositionPnL]: 持仓盈亏列表
		"""
		positions = await self.position_repo.get_by_account_id(account_id)

		pnl_list = []
		for position in positions:
			if position.volume <= 0:
				continue

			# 计算持仓盈亏
			cost_basis = Decimal(str(position.cost_price)) * Decimal(str(position.volume))

			if position.last_price:
				market_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))
				unrealized_pnl = market_value - cost_basis
				unrealized_pnl_rate = unrealized_pnl / cost_basis if cost_basis != 0 else Decimal('0')
			else:
				market_value = Decimal('0')
				unrealized_pnl = Decimal('0')
				unrealized_pnl_rate = Decimal('0')

			# 计算已实现盈亏（需要从成交记录计算）
			realized_pnl = await self._calculate_realized_pnl(account_id, position.ts_code)

			pnl_list.append(PositionPnL(
				ts_code=position.ts_code,
				position_id=position.id,
				volume=position.volume,
				cost_price=Decimal(str(position.cost_price)),
				last_price=Decimal(str(position.last_price)) if position.last_price else None,
				market_value=market_value,
				cost_basis=cost_basis,
				unrealized_pnl=Decimal(str(position.pnl)) if position.pnl else unrealized_pnl,
				unrealized_pnl_rate=Decimal(str(position.pnl_rate)) if position.pnl_rate else unrealized_pnl_rate,
				realized_pnl=realized_pnl,
				total_pnl=Decimal(str(position.pnl)) + realized_pnl if position.pnl else unrealized_pnl + realized_pnl,
				last_update=position.last_update
			))

		return pnl_list

	async def _calculate_realized_pnl (self, account_id: int, ts_code: str) -> Decimal:
		"""
		计算已实现盈亏

		Args:
			account_id: 账户ID
			ts_code: 证券代码

		Returns:
			Decimal: 已实现盈亏
		"""
		# 获取该证券的所有成交记录
		trades = await self.trade_repo.get_by_account_and_stock(account_id, ts_code)

		# 使用FIFO方法计算已实现盈亏
		# 简化实现：直接使用数据库中的计算值
		# 实际需要根据成交记录和成本计算

		realized_pnl = Decimal('0')
		buy_trades = []
		sell_trades = []

		for trade in trades:
			if trade.order.direction == 'buy':
				buy_trades.append({
					'price': Decimal(str(trade.price)),
					'volume': trade.volume,
					'time': trade.trade_time
				})
			else:
				sell_trades.append({
					'price': Decimal(str(trade.price)),
					'volume': trade.volume,
					'time': trade.trade_time
				})

		# 按时间排序
		buy_trades.sort(key=lambda x: x['time'])
		sell_trades.sort(key=lambda x: x['time'])

		# FIFO匹配
		for sell in sell_trades:
			sell_volume = sell['volume']
			sell_price = sell['price']

			while sell_volume > 0 and buy_trades:
				buy = buy_trades[0]
				buy_volume = buy['volume']
				buy_price = buy['price']

				match_volume = min(sell_volume, buy_volume)
				realized_pnl += match_volume * (sell_price - buy_price)

				# 更新剩余数量
				sell_volume -= match_volume
				buy['volume'] -= match_volume

				if buy['volume'] == 0:
					buy_trades.pop(0)

			if sell_volume > 0:
				# 仍有卖出未匹配（可能是融券卖出）
				# 简化处理：按最新价计算
				pass

		return realized_pnl

	async def calculate_daily_pnl (self, account_id: int, trade_date: date) -> DailyPnLSummary:
		"""
		计算日度盈亏

		Args:
			account_id: 账户ID
			trade_date: 交易日

		Returns:
			DailyPnLSummary: 日度盈亏摘要
		"""
		# 获取前一日持仓
		prev_date = trade_date - timedelta(days=1)

		# 获取当日成交记录
		trades = await self.trade_repo.get_by_account_and_date(account_id, trade_date)

		# 计算交易盈亏
		trade_pnl = Decimal('0')
		trade_volume = 0
		trade_amount = Decimal('0')

		for trade in trades:
			# 简化计算：卖出成交才有盈亏
			if trade.order.direction == 'sell':
				# 获取成本价（需要从持仓成本计算）
				# 这里简化：使用订单价格估算
				cost_price = await self._get_cost_price(account_id, trade.ts_code, trade_date)
				if cost_price:
					trade_pnl += Decimal(str(trade.volume)) * (
							Decimal(str(trade.price)) - cost_price
					)

			trade_volume += trade.volume
			trade_amount += Decimal(str(trade.volume)) * Decimal(str(trade.price))

		# 计算持仓盈亏变化
		# 需要获取当日和前一日持仓市值
		# 简化实现

		return DailyPnLSummary(
			trade_date=trade_date,
			trade_pnl=trade_pnl,
			position_pnl_change=Decimal('0'),  # 需要实际计算
			total_pnl=trade_pnl,  # 简化
			trade_volume=trade_volume,
			trade_amount=trade_amount,
			commission=sum(Decimal(str(t.commission)) for t in trades),
			tax=sum(Decimal(str(t.tax)) for t in trades)
		)

	async def _get_cost_price (self, account_id: int, ts_code: str, as_of_date: date) -> Optional[Decimal]:
		"""
		获取成本价

		Args:
			account_id: 账户ID
			ts_code: 证券代码
			as_of_date: 截止日期

		Returns:
			Optional[Decimal]: 成本价，如果不存在则返回None
		"""
		# 获取指定日期的持仓
		positions = await self.position_repo.get_account_positions_by_date(
			account_id, as_of_date
		)

		for position in positions:
			if position.ts_code == ts_code and position.volume > 0:
				return Decimal(str(position.cost_price))

		return None

	async def calculate_pnl_analysis (self, account_id: int, start_date: date, end_date: date) -> PnLAnalysis:
		"""
		计算盈亏分析

		Args:
			account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			PnLAnalysis: 盈亏分析结果
		"""
		# 获取期间内的所有成交
		all_trades = []
		current_date = start_date

		while current_date <= end_date:
			trades = await self.trade_repo.get_by_account_and_date(account_id, current_date)
			all_trades.extend(trades)
			current_date += timedelta(days=1)

		# 计算各种统计指标
		buy_trades = [t for t in all_trades if t.order.direction == 'buy']
		sell_trades = [t for t in all_trades if t.order.direction == 'sell']

		# 计算胜率
		winning_trades = 0
		total_sell_trades = len(sell_trades)

		# 计算平均盈亏
		total_pnl = Decimal('0')
		pnl_values = []

		for trade in all_trades:
			# 这里简化计算，实际需要匹配买卖
			pnl = await self._calculate_trade_pnl(trade)
			total_pnl += pnl
			pnl_values.append(float(pnl))

			if trade.order.direction == 'sell' and pnl > 0:
				winning_trades += 1

		win_rate = winning_trades / total_sell_trades if total_sell_trades > 0 else 0

		# 计算盈亏比
		positive_pnl = [p for p in pnl_values if p > 0]
		negative_pnl = [p for p in pnl_values if p < 0]

		avg_win = sum(positive_pnl) / len(positive_pnl) if positive_pnl else 0
		avg_loss = sum(negative_pnl) / len(negative_pnl) if negative_pnl else 0

		profit_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0

		return PnLAnalysis(
			start_date=start_date,
			end_date=end_date,
			total_trades=len(all_trades),
			win_rate=Decimal(str(win_rate)),
			total_pnl=Decimal(str(total_pnl)),
			avg_pnl_per_trade=Decimal(str(total_pnl / len(all_trades))) if all_trades else Decimal('0'),
			profit_ratio=Decimal(str(profit_ratio)),
			max_winning_trade=Decimal(str(max(pnl_values))) if pnl_values else Decimal('0'),
			max_losing_trade=Decimal(str(min(pnl_values))) if pnl_values else Decimal('0'),
			sharpe_ratio=self._calculate_sharpe_ratio(pnl_values),
			sortino_ratio=self._calculate_sortino_ratio(pnl_values)
		)

	async def _calculate_trade_pnl (self, trade) -> Decimal:
		"""
		计算单笔交易盈亏

		Args:
			trade: 成交记录

		Returns:
			Decimal: 交易盈亏
		"""
		if trade.order.direction == 'buy':
			return Decimal('0')  # 买入无盈亏

		# 卖出交易：需要计算成本
		# 简化：使用平均成本
		cost_price = await self._get_cost_price(
			trade.order.account_id,
			trade.ts_code,
			trade.trade_time.date()
		)

		if cost_price:
			pnl = Decimal(str(trade.volume)) * (
					Decimal(str(trade.price)) - cost_price
			)
			# 扣除费用
			pnl -= Decimal(str(trade.commission))
			pnl -= Decimal(str(trade.tax))
			return pnl

		return Decimal('0')

	def _calculate_sharpe_ratio (self, returns: List[float], risk_free_rate: float = 0.02) -> Decimal:
		"""
		计算夏普比率

		Args:
			returns: 收益率列表
			risk_free_rate: 无风险利率

		Returns:
			Decimal: 夏普比率
		"""
		if not returns or len(returns) < 2:
			return Decimal('0')

		import numpy as np

		returns_array = np.array(returns)
		excess_returns = returns_array - risk_free_rate / 252  # 日化无风险利率

		avg_excess_return = np.mean(excess_returns)
		std_excess_return = np.std(excess_returns)

		if std_excess_return == 0:
			return Decimal('0')

		sharpe = avg_excess_return / std_excess_return * np.sqrt(252)  # 年化

		return Decimal(str(sharpe))

	def _calculate_sortino_ratio (self, returns: List[float], risk_free_rate: float = 0.02) -> Decimal:
		"""
		计算索提诺比率

		Args:
			returns: 收益率列表
			risk_free_rate: 无风险利率

		Returns:
			Decimal: 索提诺比率
		"""
		if not returns or len(returns) < 2:
			return Decimal('0')

		import numpy as np

		returns_array = np.array(returns)
		excess_returns = returns_array - risk_free_rate / 252

		avg_excess_return = np.mean(excess_returns)

		# 只计算下行标准差
		downside_returns = excess_returns[excess_returns < 0]
		if len(downside_returns) == 0:
			return Decimal('0')

		downside_std = np.std(downside_returns)

		if downside_std == 0:
			return Decimal('0')

		sortino = avg_excess_return / downside_std * np.sqrt(252)

		return Decimal(str(sortino))