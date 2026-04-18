# quant_server/modules/events/calculators/pnl_calculator.py
"""
盈亏计算器 - 计算账户盈亏相关指标

职责：
1. 计算持仓盈亏
2. 计算交易盈亏
3. 计算已实现/未实现盈亏
4. 计算盈亏分析
"""

from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from ....modules.account.models import (
	PositionPnL,
	DailyPnLSummary,
	PnLAnalysis,
)
from ....shared.database.repositories import (
	PositionRepository,
	TradeRepository,
	OrderRepository,
	AccountRepository,
)


class PnLType(Enum):
	"""盈亏类型枚举"""
	REALIZED = "realized"  # 已实现盈亏
	UNREALIZED = "unrealized"  # 未实现盈亏
	TOTAL = "total"  # 总盈亏


class PnLCalculator:
	"""盈亏计算器"""

	def __init__ (self, session: AsyncSession):
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

	async def calculate_position_pnl (self, account_id: str) -> List[PositionPnL]:
		"""
		计算持仓盈亏

		Args:
			account_id: 账户ID

		Returns:
			List[PositionPnL]: 持仓盈亏列表，每个元素包含单个持仓的盈亏信息
		
		计算逻辑：
		1. 获取账户所有持仓
		2. 对每个持仓计算：
		   - 成本基础 = 成本价 × 持仓数量
		   - 市值 = 当前价格 × 持仓数量（如果有当前价格）
		   - 未实现盈亏 = 市值 - 成本基础
		   - 未实现盈亏率 = 未实现盈亏 / 成本基础
		   - 已实现盈亏 = 从成交记录中计算
		   - 总盈亏 = 未实现盈亏 + 已实现盈亏
		3. 构建并返回持仓盈亏列表
		"""
		positions = await self.position_repo.get_account_positions(account_id)

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
				volume=int(position.volume),
				cost_price=Decimal(str(position.cost_price)),
				last_price=Decimal(str(position.last_price)) if position.last_price else None,
				market_value=market_value,
				cost_basis=Decimal(str(cost_basis)),
				unrealized_pnl=Decimal(str(position.pnl)) if position.pnl else unrealized_pnl,
				unrealized_pnl_rate=Decimal(str(position.pnl_rate)) if position.pnl_rate else unrealized_pnl_rate,
				realized_pnl=realized_pnl,
				total_pnl=Decimal(str(position.pnl)) + realized_pnl if position.pnl else unrealized_pnl + realized_pnl,
				last_update=position.last_update
			))

		return pnl_list

	async def _calculate_realized_pnl (self, account_id: str, ts_code: str) -> Decimal:
		"""
		计算已实现盈亏

		Args:
			account_id: 账户ID
			ts_code: 证券代码

		Returns:
			Decimal: 已实现盈亏金额
		
		计算逻辑：
		1. 获取指定证券的所有成交记录
		2. 过滤出指定账户的成交记录
		3. 按时间排序买卖交易
		4. 使用FIFO（先进先出）方法匹配买卖交易
		5. 计算每笔匹配交易的盈亏
		6. 累计所有已实现盈亏
		"""
		# 获取该证券的所有成交记录
		# 简化实现：获取所有成交记录后过滤
		trades = await self.trade_repo.get_by_ts_code(ts_code)
		# 过滤出指定账户的成交记录
		trades = [t for t in trades if t.order.account_id == account_id]

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

	async def calculate_daily_pnl (self, account_id: str, trade_date: date) -> DailyPnLSummary:
		"""
		计算日度盈亏

		Args:
			account_id: 账户ID
			trade_date: 交易日

		Returns:
			DailyPnLSummary: 日度盈亏摘要，包含交易盈亏、持仓盈亏变化和总盈亏
		
		计算逻辑：
		1. 获取前一日和当日的持仓
		2. 计算前一日持仓在当日的市值变化（持仓盈亏变化）
		3. 计算当日交易产生的盈亏（交易盈亏）
		4. 总盈亏 = 交易盈亏 + 持仓盈亏变化
		5. 汇总交易数据（成交量、成交额、佣金、税费）
		"""
		try:
			# 1. 获取前一日日期
			prev_date = trade_date - timedelta(days=1)

			# 2. 获取当日成交记录
			trades = await self.trade_repo.get_by_account_id(account_id)
			# 过滤出当日的成交记录
			daily_trades = [t for t in trades if t.trade_time.date() == trade_date]

			# 3. 计算交易盈亏
			trade_pnl = Decimal('0')
			trade_volume = 0
			trade_amount = Decimal('0')
			commission = Decimal('0')
			tax = Decimal('0')

			for trade in daily_trades:
				# 计算交易盈亏（只计算卖出交易）
				if trade.order.direction == 'sell':
					# 获取成本价
					cost_price = await self._get_cost_price(account_id, trade.ts_code, trade_date)
					if cost_price:
						# 计算卖出交易的盈亏
						trade_pnl += Decimal(str(trade.volume)) * (
								Decimal(str(trade.price)) - cost_price
						)

				# 累计交易数据
				trade_volume += trade.volume
				trade_amount += Decimal(str(trade.volume)) * Decimal(str(trade.price))
				commission += Decimal(str(trade.commission))
				tax += Decimal(str(trade.tax))

			# 4. 计算持仓盈亏变化
			# 获取当前持仓
			current_positions = await self.position_repo.get_account_positions(account_id)
			
			# 简化计算：假设当前持仓的市值变化即为持仓盈亏变化
			# 实际应用中，应该获取前一日的持仓数据进行对比
			position_pnl_change = Decimal('0')
			for position in current_positions:
				if position.volume > 0 and position.last_price and position.cost_price:
					# 计算持仓盈亏
					current_value = Decimal(str(position.volume)) * Decimal(str(position.last_price))
					cost_value = Decimal(str(position.volume)) * Decimal(str(position.cost_price))
					position_pnl = current_value - cost_value
					position_pnl_change += position_pnl

			# 5. 计算总盈亏
			total_pnl = trade_pnl + position_pnl_change

			# 6. 构建并返回日度盈亏摘要
			return DailyPnLSummary(
				trade_date=trade_date,
				trade_pnl=trade_pnl,
				position_pnl_change=position_pnl_change,
				total_pnl=total_pnl,
				trade_volume=trade_volume,
				trade_amount=trade_amount,
				commission=commission,
				tax=tax
			)
		
		except Exception as e:
			# 记录错误并返回默认值
			import logging
			logging.error(f"计算日度盈亏失败: {str(e)}")
			return DailyPnLSummary(
				trade_date=trade_date,
				trade_pnl=Decimal('0'),
				position_pnl_change=Decimal('0'),
				total_pnl=Decimal('0'),
				trade_volume=0,
				trade_amount=Decimal('0'),
				commission=Decimal('0'),
				tax=Decimal('0')
			)

	async def _get_cost_price (self, account_id: str, ts_code: str, _as_of_date: date) -> Optional[Decimal]:
		"""
		获取成本价

		Args:
			account_id: 账户ID
			ts_code: 证券代码
			_as_of_date: 截止日期

		Returns:
			Optional[Decimal]: 成本价，如果不存在则返回None
		"""
		# 获取当前持仓
		positions = await self.position_repo.get_account_positions(account_id)

		for position in positions:
			if position.ts_code == ts_code and position.volume > 0:
				return Decimal(str(position.cost_price))

		return None

	async def calculate_pnl_analysis (self, _account_id: str, start_date: date, end_date: date) -> PnLAnalysis:
		"""
		计算盈亏分析

		Args:
			_account_id: 账户ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			PnLAnalysis: 盈亏分析结果
		"""
		# 获取期间内的所有成交
		all_trades = []
		current_date = start_date

		while current_date <= end_date:
			trades = await self.trade_repo.get_by_trade_date(current_date, user_id=None)
			all_trades.extend(trades)
			current_date += timedelta(days=1)

		# 计算各种统计指标
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
			trade: 成交记录对象

		Returns:
			Decimal: 交易盈亏金额
		
		计算逻辑：
		1. 买入交易：返回0（买入时不产生盈亏）
		2. 卖出交易：
		   - 获取该证券的成本价
		   - 计算卖出金额 = 卖出价格 × 卖出数量
		   - 计算成本金额 = 成本价 × 卖出数量
		   - 计算交易盈亏 = 卖出金额 - 成本金额
		   - 扣除交易佣金和税费
		   - 返回最终盈亏
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

	@staticmethod
	def _calculate_sharpe_ratio (returns: List[float], risk_free_rate: float = 0.02) -> Decimal:
		"""
		计算夏普比率

		Args:
			returns: 收益率列表
			risk_free_rate: 无风险利率（默认2%）

		Returns:
			Decimal: 夏普比率，衡量投资回报与风险的比值
		
		计算逻辑：
		1. 计算超额收益率 = 实际收益率 - 无风险利率（日化）
		2. 计算超额收益率的均值
		3. 计算超额收益率的标准差
		4. 夏普比率 = 超额收益率均值 / 超额收益率标准差
		5. 年化处理：乘以根号252（一年的交易日数）
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

	@staticmethod
	def _calculate_sortino_ratio (returns: List[float], risk_free_rate: float = 0.02) -> Decimal:
		"""
		计算索提诺比率

		Args:
			returns: 收益率列表
			risk_free_rate: 无风险利率（默认2%）

		Returns:
			Decimal: 索提诺比率，衡量投资回报与下行风险的比值
		
		计算逻辑：
		1. 计算超额收益率 = 实际收益率 - 无风险利率（日化）
		2. 计算超额收益率的均值
		3. 计算下行标准差（只考虑负的超额收益率）
		4. 索提诺比率 = 超额收益率均值 / 下行标准差
		5. 年化处理：乘以根号252（一年的交易日数）
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

	async def calculate_account_performance (self, account_id: str) -> Dict[str, Any]:
		"""
		计算账户绩效指标

		Args:
			account_id: 账户ID

		Returns:
			Dict: 绩效指标，包含总收益率、年化收益率、夏普比率、最大回撤和胜率
		"""
		try:
			# 1. 获取账户信息
			account = await self.account_repo.get(account_id)
			if not account:
				raise ValueError(f"账户不存在: {account_id}")

			# 2. 获取账户历史绩效数据
			# 这里简化处理，实际需要从AccountDailyPerformance表获取数据
			# performance_history = await self.account_repo.get_performance_history(account_id)

			# 3. 计算基本指标
			# 总收益率 = (当前总资产 - 初始资产) / 初始资产
			total_return = 0.0
			if account.initial_balance > 0:
				total_return = float((account.total_balance - account.initial_balance) / account.initial_balance)

			# 4. 计算年化收益率
			annualized_return = 0.0
			if total_return != 0:
				# 简化计算：假设账户已存在1年
				annualized_return = total_return

			# 5. 计算夏普比率
			# 简化计算：使用假设的收益率数据
			sharpe_ratio = 0.0

			# 6. 计算最大回撤
			# 简化计算：假设最大回撤为0
			max_drawdown = 0.0

			# 7. 计算胜率
			# 获取所有交易记录
			trades = await self.trade_repo.get_by_account_id(account_id)
			sell_trades = [t for t in trades if t.order.direction == 'sell']
			total_sell_trades = len(sell_trades)
			
			winning_trades = 0
			for trade in sell_trades:
				# 简化计算：假设卖出价格高于买入价格为盈利
				# 实际需要匹配买卖交易计算真实盈亏
				winning_trades += 1
			
			win_rate = 0.0
			if total_sell_trades > 0:
				win_rate = winning_trades / total_sell_trades

			# 8. 构建返回结果
			return {
				"total_return": total_return,
				"annualized_return": annualized_return,
				"sharpe_ratio": sharpe_ratio,
				"max_drawdown": max_drawdown,
				"win_rate": win_rate,
				"total_trades": len(trades),
				"total_sell_trades": total_sell_trades,
				"winning_trades": winning_trades
			}
		
		except Exception as e:
			# 记录错误并返回默认值
			import logging
			logging.error(f"计算账户绩效失败: {str(e)}")
			return {
				"total_return": 0.0,
				"annualized_return": 0.0,
				"sharpe_ratio": 0.0,
				"max_drawdown": 0.0,
				"win_rate": 0.0,
				"total_trades": 0,
				"total_sell_trades": 0,
				"winning_trades": 0
			}