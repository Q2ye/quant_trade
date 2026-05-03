#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易分析服务

负责分析交易行为、执行质量和交易成本，提供多维度的交易诊断。

分析维度：
----------
1. **交易统计** — 盈亏分布、胜率、盈亏比
   - 分类统计：盈利/亏损/盈亏平衡交易数量
   - 注意：依赖 trade 对象具有 pnl 属性，缺失时归入盈亏平衡

2. **交易成本分析** — 佣金、印花税、滑点、冲击成本
   - 成本分解：佣金 + 税费 + 滑点（估算为交易额的 0.1%）
   - 成本效率：成本率 = 总成本 / 总交易额
   - 按买卖方向分别计算成本率

3. **执行质量分析** — 成交速度、成交率、价格改进
   - 成交率 = 已成交订单 / 总订单
   - 执行时间 = filled_at - submitted_at（秒）
   - 价格改进：买入时成交价低于委托价为正，卖出时成交价高于委托价为正

4. **交易行为分析** — 交易规模、持仓周期、换手率
   - 平均交易规模 = mean(volume × price)
   - 持仓周期和换手率需基于实际交易时间计算（当前为近似值）

5. **交易时间分布** — 日内时段分布、周内日期分布
   - 早盘 9:00-11:59、午盘 13:00-14:59、其他时段

6. **交易模式识别** — 集中交易、反转、动量、季节性
   - 集中模式：同一证券交易次数 ≥ 10
   - 反转/动量模式：基于交易序列特征简化判断
   - 季节性模式：按月份统计交易活跃度
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Any

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.models import TradeAnalysis
from shared.database.repositories import AccountRepository
from shared.database.repositories import OrderRepository
from shared.database.repositories import PositionRepository
from shared.database.repositories import TradeRepository

logger = logging.getLogger(__name__)


class TradeAnalysisService:
	"""交易分析服务

	提供交易记录的多维度分析，包括盈亏统计、成本计算、执行质量评估、
	交易行为分析和交易模式识别。

	"""

	def __init__ (
			self,
			session: AsyncSession,
			trade_repo: TradeRepository = None,
			order_repo: OrderRepository = None,
			position_repo: PositionRepository = None,
			account_repo: AccountRepository = None
	):
		"""
		初始化交易分析服务

		Args:
			session: 异步数据库会话
			trade_repo: 交易 Repository（可选，默认根据 session 创建）
			order_repo: 订单 Repository（可选）
			position_repo: 持仓 Repository（可选）
			account_repo: 账户 Repository（可选）
		"""
		self.session = session
		self.trade_repo = trade_repo or TradeRepository(session)
		self.order_repo = order_repo or OrderRepository(session)
		self.position_repo = position_repo or PositionRepository(session)
		self.account_repo = account_repo or AccountRepository(session)

	# =========================================================================
	# 公有方法 — 交易分析入口
	# =========================================================================

	async def analyze_trades (
			self,
			strategy_id: str,
			account_id: str,
			start_date: datetime,
			end_date: datetime
	) -> TradeAnalysis:
		"""分析指定策略和账户在区间内的全部交易

		汇总交易统计、成本、执行质量、行为、时间分布和模式识别，
		构建完整的 TradeAnalysis 结果对象。

		数据获取逻辑：
		- 优先按 strategy_id + account_id 联合查询
		- 无结果时回退到仅按 account_id 查询（兼容无策略关联的交易记录）

		Args:
			strategy_id: 策略 ID
			account_id: 账户 ID
			start_date: 分析区间起始日期
			end_date: 分析区间结束日期

		Returns:
			TradeAnalysis: 包含所有分析维度的交易分析结果

		Raises:
			ValueError: 未找到任何交易记录时抛出
		"""
		try:
			# 1. 获取交易记录
			trades = await self.trade_repo.get_by_strategy_and_account(
				strategy_id, account_id, start_date, end_date
			)

			if not trades:
				trades = await self.trade_repo.get_by_account_id(
					account_id,
					start_time=datetime.combine(start_date, datetime.min.time()) if start_date else None,
					end_time=datetime.combine(end_date, datetime.max.time()) if end_date else None
				)

			if not trades:
				raise ValueError("没有找到交易记录")

			# 2. 获取订单信息（用于执行质量分析）
			orders = await self.order_repo.get_by_strategy_and_account(
				strategy_id, account_id, start_date, end_date
			)

			# 3. 各维度分析
			trade_stats = self._analyze_trade_statistics(trades)

			# 使用统一的成本计算方法（消除重复逻辑）
			cost_analysis = self._calc_cost_breakdown(trades)

			execution_quality = await self._calc_execution_quality(orders)

			trading_behavior = self._analyze_trading_behavior(trades, account_id, start_date, end_date)

			time_distribution = self._analyze_time_distribution(trades)

			trading_patterns = await self._identify_trading_patterns(trades)

			# 4. 构建分析结果
			analysis = TradeAnalysis(
				analysis_id=f"trade_{strategy_id}_{account_id}_{start_date}_{end_date}",
				strategy_id=strategy_id,
				account_id=account_id,
				analysis_period=f"{start_date} 至 {end_date}",
				total_trades=trade_stats['total_trades'],
				winning_trades=trade_stats['winning_trades'],
				losing_trades=trade_stats['losing_trades'],
				breakeven_trades=trade_stats['breakeven_trades'],
				total_commission=Decimal(str(cost_analysis['total_commission'])),
				total_tax=Decimal(str(cost_analysis['total_tax'])),
				total_slippage=Decimal(str(cost_analysis['total_slippage'])),
				total_trading_cost=Decimal(str(cost_analysis['total_trading_cost'])),
				average_execution_time=Decimal(str(execution_quality['average_execution_time'])),
				fill_rate=Decimal(str(execution_quality['fill_rate'])),
				price_improvement=Decimal(str(execution_quality['price_improvement'])),
				average_trade_size=Decimal(str(trading_behavior['average_trade_size'])),
				average_holding_period=Decimal(str(trading_behavior['average_holding_period'])),
				turnover_rate=Decimal(str(trading_behavior['turnover_rate'])),
				time_of_day_distribution=time_distribution['time_of_day'],
				day_of_week_distribution=time_distribution['day_of_week'],
				trading_patterns=trading_patterns,
				cost_breakdown=cost_analysis['breakdown'],
				cost_efficiency=cost_analysis['efficiency']
			)

			return analysis

		except Exception as e:
			raise ValueError(f"交易分析失败: {str(e)}")

	async def analyze_execution_quality (
			self,
			order_ids: List[str],
			benchmark_prices: Dict[str, float] = None
	) -> Dict[str, Any]:
		"""分析订单执行质量

		对指定订单列表进行执行质量评估，包括成交率、执行耗时、
		价格改进和实现缺口。

		指标定义：
		- 成交率（fill_rate）：filled 订单数 / 总订单数
		- 价格改进（price_improvement）：
		  买入：委托价 - 成交均价（正值为改进）
		  卖出：成交均价 - 委托价（正值为改进）
		- 实现缺口（implementation_shortfall）：
		  买入：成交均价 - 基准价
		  卖出：基准价 - 成交均价

		Args:
			order_ids: 待分析的订单 ID 列表
			benchmark_prices: 基准价格字典 {ts_code: price}，用于计算实现缺口

		Returns:
			Dict: 包含 total_orders, filled_orders, cancelled_orders, rejected_orders,
				  fill_rate, average_execution_time, median_execution_time,
				  price_improvement, implementation_shortfall 等指标

		Raises:
			ValueError: 未找到任何订单时抛出
		"""
		try:
			orders = []
			for order_id in order_ids:
				order = await self.order_repo.get(order_id)
				if order:
					orders.append(order)

			if not orders:
				raise ValueError("没有找到订单")

			# 分析执行时间
			execution_times = []
			filled_orders = [o for o in orders if o.status == 'filled']

			for order in filled_orders:
				if order.submitted_at and order.filled_at:
					exec_time = (order.filled_at - order.submitted_at).total_seconds()
					execution_times.append(exec_time)

			# 分析价格改进
			price_improvements = []
			for order in filled_orders:
				if hasattr(order, 'price') and hasattr(order, 'avg_price'):
					if order.price and order.avg_price:
						if order.direction == 'buy':
							# 买入：成交均价低于委托价为改进
							improvement = float(order.price - order.avg_price)
						else:
							# 卖出：成交均价高于委托价为改进
							improvement = float(order.avg_price - order.price)
						price_improvements.append(improvement)

			# 分析实现缺口（需要基准价格）
			implementation_shortfalls = []
			for order in filled_orders:
				if benchmark_prices and order.ts_code in benchmark_prices:
					benchmark_price = benchmark_prices[order.ts_code]
					if order.avg_price:
						if order.direction == 'buy':
							shortfall = float(order.avg_price - benchmark_price)
						else:
							shortfall = float(benchmark_price - order.avg_price)
						implementation_shortfalls.append(shortfall)

			return {
				'total_orders': len(orders),
				'filled_orders': len(filled_orders),
				'cancelled_orders': len([o for o in orders if o.status == 'cancelled']),
				'rejected_orders': len([o for o in orders if o.status == 'rejected']),
				'fill_rate': len(filled_orders) / len(orders) if orders else 0,
				'average_execution_time': np.mean(execution_times) if execution_times else 0,
				'median_execution_time': np.median(execution_times) if execution_times else 0,
				'price_improvement': np.mean(price_improvements) if price_improvements else 0,
				'implementation_shortfall': np.mean(implementation_shortfalls) if implementation_shortfalls else 0,
				'execution_times': execution_times,
				'price_improvements': price_improvements
			}

		except Exception as e:
			raise ValueError(f"执行质量分析失败: {str(e)}")

	async def analyze_trading_costs (
			self,
			account_id: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""分析账户在指定区间的交易成本

		从数据库获取交易记录，计算佣金、税费、滑点成本，
		并按买卖方向分解成本率。

		成本构成：
		- 佣金（commission）：来自 trade 对象
		- 税费（tax）：来自 trade 对象
		- 滑点（slippage）：估算为总交易额的 0.1%

		Args:
			account_id: 账户 ID
			start_date: 起始日期
			end_date: 结束日期

		Returns:
			Dict: 包含 total_commission, total_tax, total_slippage,
				  total_trading_cost, breakdown, efficiency

		Raises:
			ValueError: 成本计算失败时抛出
		"""
		try:
			trades = await self.trade_repo.get_by_account_id(
				account_id,
				start_time=datetime.combine(start_date, datetime.min.time()) if start_date else None,
				end_time=datetime.combine(end_date, datetime.max.time()) if end_date else None,
				with_order=True
			)

			if not trades:
				return {
					'total_commission': 0,
					'total_tax': 0,
					'total_slippage': 0,
					'total_trading_cost': 0,
					'breakdown': {},
					'efficiency': {}
				}

			# 使用统一的成本计算方法
			result = self._calc_cost_breakdown(trades)

			# 按买卖方向分解成本率
			buy_trades = [t for t in trades if hasattr(t, 'order') and t.order and t.order.direction == 'buy']
			sell_trades = [t for t in trades if hasattr(t, 'order') and t.order and t.order.direction == 'sell']

			efficiency = result['efficiency']

			if buy_trades:
				buy_value = sum(
					t.price * t.volume for t in buy_trades
					if hasattr(t, 'price') and hasattr(t, 'volume')
				)
				buy_cost = sum(
					t.commission + t.tax for t in buy_trades
					if hasattr(t, 'commission') and hasattr(t, 'tax')
				)
				if buy_value > 0:
					efficiency['buy_cost_rate'] = float(buy_cost / buy_value)

			if sell_trades:
				sell_value = sum(
					t.price * t.volume for t in sell_trades
					if hasattr(t, 'price') and hasattr(t, 'volume')
				)
				sell_cost = sum(
					t.commission + t.tax for t in sell_trades
					if hasattr(t, 'commission') and hasattr(t, 'tax')
				)
				if sell_value > 0:
					efficiency['sell_cost_rate'] = float(sell_cost / sell_value)

			result['efficiency'] = efficiency
			return result

		except Exception as e:
			raise ValueError(f"交易成本分析失败: {str(e)}")

	async def analyze_trading_patterns (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date,
			pattern_types: List[str] = None
	) -> List[Dict[str, Any]]:
		"""识别策略的交易模式

		支持四种模式识别：
		- concentration：集中交易（同一证券频繁交易）
		- reversal：反转交易模式
		- momentum：动量交易模式
		- seasonality：季节性交易模式（按月统计）

		Args:
			strategy_id: 策略 ID
			start_date: 起始日期
			end_date: 结束日期
			pattern_types: 需要识别的模式类型列表，默认全部

		Returns:
			识别到的交易模式列表，每项含 pattern_type, description 等字段

		Raises:
			ValueError: 模式识别失败时抛出
		"""
		try:
			trades = await self.trade_repo.get_by_strategy_id(
				strategy_id,
				start_time=datetime.combine(start_date, datetime.min.time()) if start_date else None,
				end_time=datetime.combine(end_date, datetime.max.time()) if end_date else None
			)

			if not trades:
				return []

			if pattern_types is None:
				pattern_types = ['concentration', 'reversal', 'momentum', 'seasonality']

			patterns = []

			if 'concentration' in pattern_types:
				concentration_patterns = self._identify_concentration_patterns(trades)
				patterns.extend(concentration_patterns)

			if 'reversal' in pattern_types:
				reversal_patterns = self._identify_reversal_patterns(trades)
				patterns.extend(reversal_patterns)

			if 'momentum' in pattern_types:
				momentum_patterns = self._identify_momentum_patterns(trades)
				patterns.extend(momentum_patterns)

			if 'seasonality' in pattern_types:
				seasonality_patterns = self._identify_seasonality_patterns(trades)
				patterns.extend(seasonality_patterns)

			return patterns

		except Exception as e:
			raise ValueError(f"交易模式识别失败: {str(e)}")

	# =========================================================================
	# 静态私有方法 — 各维度分析逻辑
	# =========================================================================

	@staticmethod
	def _analyze_trade_statistics (trades: List) -> Dict[str, Any]:
		"""分析交易盈亏统计

		根据 trade 对象的 pnl 属性将交易分为盈利、亏损和盈亏平衡三类。
		若 trade 缺少 pnl 属性，归入盈亏平衡（breakeven）而非随机分配，
		确保结果可复现。

		Args:
			trades: 交易记录列表

		Returns:
			Dict: 含 total_trades, winning_trades, losing_trades,
				  breakeven_trades, win_rate
		"""
		if not trades:
			return {
				'total_trades': 0,
				'winning_trades': 0,
				'losing_trades': 0,
				'breakeven_trades': 0,
				'win_rate': 0.0
			}

		winning_trades = []
		losing_trades = []
		breakeven_trades = []

		for trade in trades:
			if hasattr(trade, 'pnl'):
				if trade.pnl > 0:
					winning_trades.append(trade)
				elif trade.pnl < 0:
					losing_trades.append(trade)
				else:
					breakeven_trades.append(trade)
			else:
				# 缺少 pnl 属性时归入盈亏平衡，不再使用随机数
				breakeven_trades.append(trade)

		# 对缺失 pnl 的交易发出警告
		missing_pnl = sum(1 for t in trades if not hasattr(t, 'pnl'))
		if missing_pnl > 0:
			logger.warning(
				f"{missing_pnl}/{len(trades)} 条交易记录缺少 pnl 属性，已归入盈亏平衡。"
				f"请确认 Trade 模型包含 pnl 字段。"
			)

		win_rate = len(winning_trades) / len(trades) if trades else 0

		return {
			'total_trades': len(trades),
			'winning_trades': len(winning_trades),
			'losing_trades': len(losing_trades),
			'breakeven_trades': len(breakeven_trades),
			'win_rate': win_rate
		}

	@staticmethod
	def _calc_cost_breakdown (trades: List) -> Dict[str, Any]:
		"""计算交易成本分解（统一的内部实现）

		从交易列表中汇总佣金、税费，估算滑点成本，计算成本效率指标。
		此方法是 analyze_trading_costs（实例）和 analyze_trades 的共享实现，
		消除代码重复。

		滑点估算：总交易额 × 0.1%（业界常用简化估算）

		Args:
			trades: 交易记录列表

		Returns:
			Dict: 含 total_commission, total_tax, total_slippage,
				  total_trading_cost, breakdown, efficiency
		"""
		# 汇总佣金和税费
		total_commission = sum(
			t.commission for t in trades
			if hasattr(t, 'commission')
		)
		total_tax = sum(
			t.tax for t in trades
			if hasattr(t, 'tax')
		)

		# 估算滑点成本（总交易额的 0.1%）
		total_slippage = TradeAnalysisService._estimate_slippage_cost(trades)

		total_trading_cost = total_commission + total_tax + total_slippage

		# 成本分解
		breakdown = {
			'commission': float(total_commission),
			'tax': float(total_tax),
			'slippage': float(total_slippage),
			'impact_cost': 0.0,
			'other': 0.0
		}

		# 成本效率指标
		total_trade_value = sum(
			t.price * t.volume for t in trades
			if hasattr(t, 'price') and hasattr(t, 'volume')
		)

		efficiency = {}
		if total_trade_value > 0:
			efficiency['cost_rate'] = float(total_trading_cost / total_trade_value)
			efficiency['commission_rate'] = float(total_commission / total_trade_value)
			efficiency['tax_rate'] = float(total_tax / total_trade_value)

		return {
			'total_commission': total_commission,
			'total_tax': total_tax,
			'total_slippage': total_slippage,
			'total_trading_cost': total_trading_cost,
			'breakdown': breakdown,
			'efficiency': efficiency
		}

	@staticmethod
	async def _calc_execution_quality (orders: List) -> Dict[str, float]:
		"""计算订单执行质量指标

		从订单列表中提取成交率、平均执行时间和价格改进。

		Args:
			orders: 订单列表

		Returns:
			Dict: 含 average_execution_time, fill_rate, price_improvement,
				  implementation_shortfall
		"""
		if not orders:
			return {
				'average_execution_time': 0.0,
				'fill_rate': 0.0,
				'price_improvement': 0.0,
				'implementation_shortfall': 0.0
			}

		# 成交率
		filled_orders = [o for o in orders if o.status == 'filled']
		fill_rate = len(filled_orders) / len(orders) if orders else 0

		# 平均执行时间
		execution_times = []
		for order in filled_orders:
			if hasattr(order, 'submitted_at') and hasattr(order, 'filled_at'):
				if order.submitted_at and order.filled_at:
					exec_time = (order.filled_at - order.submitted_at).total_seconds()
					execution_times.append(exec_time)

		average_execution_time = np.mean(execution_times) if execution_times else 0

		# 价格改进
		price_improvements = []
		for order in filled_orders:
			if hasattr(order, 'price') and hasattr(order, 'avg_price'):
				if order.price and order.avg_price:
					if order.direction == 'buy':
						improvement = float(order.price - order.avg_price)
					else:
						improvement = float(order.avg_price - order.price)
					price_improvements.append(improvement)

		price_improvement = np.mean(price_improvements) if price_improvements else 0

		return {
			'average_execution_time': average_execution_time,
			'fill_rate': fill_rate,
			'price_improvement': price_improvement,
			'implementation_shortfall': 0.0  # 需要基准价格，此处留空
		}

	@staticmethod
	def _analyze_trading_behavior (
			trades: List,
			account_id: str = None,
			start_date: date = None,
			end_date: date = None
	) -> Dict[str, float]:
		"""分析交易行为特征

		计算平均交易规模（volume × price 的均值）、平均持仓周期和换手率。

		注意：
		- 平均持仓周期当前为简化估算值，实际应从持仓表计算每笔交易的进出时间差
		- 换手率基于交易天数计算，若未提供 start_date/end_date 则假定 30 天窗口

		Args:
			trades: 交易记录列表
			start_date: 区间起始日期（用于计算换手率）
			end_date: 区间结束日期（用于计算换手率）

		Returns:
			Dict: 含 average_trade_size, average_holding_period, turnover_rate
		"""
		if not trades:
			return {
				'average_trade_size': 0.0,
				'average_holding_period': 0.0,
				'turnover_rate': 0.0
			}

		# 平均交易规模（金额）
		trade_sizes = []
		for trade in trades:
			if hasattr(trade, 'volume') and hasattr(trade, 'price'):
				trade_size = trade.volume * trade.price
				trade_sizes.append(trade_size)

		average_trade_size = np.mean(trade_sizes) if trade_sizes else 0

		# Compute average holding period from trade timestamps per stock
		holding_periods = []
		if trades:
			trades_by_code: Dict[str, List] = {}
			for trade in trades:
				if hasattr(trade, "ts_code") and hasattr(trade, "trade_time") and trade.trade_time:
					code = trade.ts_code
					if code not in trades_by_code:
						trades_by_code[code] = []
					trades_by_code[code].append(trade.trade_time)
			for code, times in trades_by_code.items():
				if len(times) >= 2:
					holding_days = (max(times) - min(times)).total_seconds() / 86400
					holding_periods.append(holding_days)
				else:
					# Single trade per stock: estimate from analysis period
					if start_date and end_date:
						holding_periods.append((end_date - start_date).days / 2)
					else:
						holding_periods.append(3.0)
		average_holding_period = np.mean(holding_periods) if holding_periods else 0.0

		# 换手率 = 交易次数 / 交易天数
		if start_date and end_date:
			trading_days = max((end_date - start_date).days, 1)
		else:
			trading_days = 30  # 默认假定 30 天窗口
		turnover_rate = len(trades) / trading_days

		return {
			'average_trade_size': average_trade_size,
			'average_holding_period': average_holding_period,
			'turnover_rate': turnover_rate
		}

	@staticmethod
	def _analyze_time_distribution (trades: List) -> Dict[str, Dict[str, int]]:
		"""分析交易时间分布

		将交易按日内时段（早盘/午盘/其他）和周几进行分类统计。

		Args:
			trades: 交易记录列表

		Returns:
			Dict: 含 time_of_day {morning/afternoon/other: count}
				  和 day_of_week {Monday-Weekend: count}
		"""
		time_of_day = {'morning': 0, 'afternoon': 0, 'other': 0}
		day_of_week = {
			'Monday': 0, 'Tuesday': 0, 'Wednesday': 0,
			'Thursday': 0, 'Friday': 0, 'Weekend': 0
		}

		for trade in trades:
			if hasattr(trade, 'trade_time'):
				trade_time = trade.trade_time

				# 日内时段分类
				hour = trade_time.hour
				if 9 <= hour < 12:
					time_of_day['morning'] += 1
				elif 13 <= hour < 15:
					time_of_day['afternoon'] += 1
				else:
					time_of_day['other'] += 1

				# 周几分类
				weekday = trade_time.strftime('%A')
				if weekday in day_of_week:
					day_of_week[weekday] += 1
				else:
					day_of_week['Weekend'] += 1

		return {
			'time_of_day': time_of_day,
			'day_of_week': day_of_week
		}

	# =========================================================================
	# 私有方法 — 交易模式识别
	# =========================================================================

	async def _identify_trading_patterns (self, trades: List) -> List[Dict[str, Any]]:
		"""识别交易模式（综合入口）

		当前实现识别集中交易模式，未来可扩展更多模式类型。

		Args:
			trades: 交易记录列表

		Returns:
			交易模式列表
		"""
		patterns = []
		concentration_patterns = self._identify_concentration_patterns(trades)
		patterns.extend(concentration_patterns)
		return patterns

	@staticmethod
	def _identify_concentration_patterns (trades: List) -> List[Dict[str, Any]]:
		"""识别集中交易模式

		按 ts_code 分组，对同一证券交易次数 ≥ 10 的标记为集中交易。
		这表明策略可能在特定标的上过度集中，需关注分散化程度。

		Args:
			trades: 交易记录列表

		Returns:
			集中交易模式列表，每项含 pattern_type, code, trade_count, description
		"""
		patterns = []

		if not trades:
			return patterns

		# 按证券代码分组
		trades_by_code = {}
		for trade in trades:
			if hasattr(trade, 'ts_code'):
				code = trade.ts_code
				if code not in trades_by_code:
					trades_by_code[code] = []
				trades_by_code[code].append(trade)

		# 标记交易次数 ≥ 10 的证券
		for code, code_trades in trades_by_code.items():
			if len(code_trades) >= 10:
				patterns.append({
					'pattern_type': 'concentration',
					'code': code,
					'trade_count': len(code_trades),
					'description': f"证券 {code} 交易集中，共 {len(code_trades)} 次交易"
				})

		return patterns

	@staticmethod
	def _identify_reversal_patterns (trades: List) -> List[Dict[str, Any]]:
		"""识别反转交易模式

		按股票分组后分析价格序列，检测"连续同向价格变动后出现反向变动"的反转特征。
		反转判定规则：
		- 同一股票连续 ≥ 2 笔交易价格朝同一方向变动后，出现反向变动
		- 反转幅度越大、前期趋势越长，置信度越高

		Args:
			trades: 交易记录列表

		Returns:
			反转交易模式列表，每项含 pattern_type, code, direction, prior_streak,
			reversal_magnitude, description, confidence
		"""
		patterns = []
		if not trades:
			return patterns

		# 按股票代码分组
		trades_by_code: Dict[str, List] = {}
		for trade in trades:
			if hasattr(trade, 'ts_code') and hasattr(trade, 'trade_time'):
				code = trade.ts_code
				if code not in trades_by_code:
					trades_by_code[code] = []
				trades_by_code[code].append(trade)

		for code, code_trades in trades_by_code.items():
			# 按时间排序，提取价格序列
			sorted_trades = sorted(
				[t for t in code_trades if hasattr(t, 'price')],
				key=lambda t: t.trade_time
			)
			if len(sorted_trades) < 3:
				continue

			# 计算相邻交易的价格变动方向
			price_changes = []
			for i in range(1, len(sorted_trades)):
				p0 = float(sorted_trades[i - 1].price)
				p1 = float(sorted_trades[i].price)
				price_changes.append({
					'direction': 'up' if p1 > p0 else ('down' if p1 < p0 else 'flat'),
					'magnitude': abs(p1 - p0),
					'pct': abs(p1 - p0) / p0 if p0 > 0 else 0
				})

			# 检测反转：连续同向变动后出现反向
			i = 0
			while i < len(price_changes) - 1:
				current_dir = price_changes[i]['direction']
				if current_dir == 'flat':
					i += 1
					continue

				# 统计同向连续长度
				streak_len = 1
				streak_magnitude = price_changes[i]['magnitude']
				j = i + 1
				while j < len(price_changes) and price_changes[j]['direction'] == current_dir:
					streak_len += 1
					streak_magnitude += price_changes[j]['magnitude']
					j += 1

				# 检查是否跟随反向变动
				if streak_len >= 2 and j < len(price_changes):
					opposite = 'down' if current_dir == 'up' else 'up'
					if price_changes[j]['direction'] == opposite:
						reversal_pct = price_changes[j]['pct']
						# 置信度：基于前期趋势长度 + 反转幅度
						confidence = min(0.5 + 0.08 * streak_len + 0.25 * min(reversal_pct * 100, 1.0), 0.95)
						patterns.append({
							'pattern_type': 'reversal',
							'code': code,
							'direction': f'{current_dir}->{opposite}',
							'prior_streak': streak_len,
							'reversal_magnitude': round(reversal_pct * 100, 4),
							'description': (
								f'证券 {code} 检测到反转：连续 {streak_len} 次'
								f'{"上涨" if current_dir == "up" else "下跌"}后出现'
								f'{"下跌" if opposite == "down" else "上涨"}，'
								f'反转幅度 {reversal_pct * 100:.2f}%'
							),
							'confidence': round(confidence, 2)
						})
				i = j  # 跳过已检测的同向段

		# 按置信度降序排列
		patterns.sort(key=lambda p: p['confidence'], reverse=True)
		return patterns

	@staticmethod
	def _identify_momentum_patterns (trades: List) -> List[Dict[str, Any]]:
		"""识别动量交易模式

		按股票分组后分析价格序列，检测持续同向价格变动（追涨/杀跌）的动量特征。
		动量判定规则：
		- 同一股票连续 ≥ 3 笔交易价格朝同一方向变动 = 动量
		- 成交量递增确认动量强度
		- 上涨动量 = 追涨，下跌动量 = 杀跌

		Args:
			trades: 交易记录列表

		Returns:
			动量交易模式列表，每项含 pattern_type, code, direction, streak_length,
			volume_confirmation, description, confidence
		"""
		patterns = []
		if not trades:
			return patterns

		# 按股票代码分组
		trades_by_code: Dict[str, List] = {}
		for trade in trades:
			if hasattr(trade, 'ts_code') and hasattr(trade, 'trade_time'):
				code = trade.ts_code
				if code not in trades_by_code:
					trades_by_code[code] = []
				trades_by_code[code].append(trade)

		for code, code_trades in trades_by_code.items():
			# 按时间排序
			sorted_trades = sorted(
				[t for t in code_trades if hasattr(t, 'price') and hasattr(t, 'volume')],
				key=lambda t: t.trade_time
			)
			if len(sorted_trades) < 3:
				continue

			# 扫描连续同向价格变动段
			i = 0
			while i < len(sorted_trades) - 1:
				p0 = float(sorted_trades[i].price)
				p1 = float(sorted_trades[i + 1].price)
				if p1 == p0:
					i += 1
					continue

				current_dir = 'up' if p1 > p0 else 'down'
				streak_len = 1
				vol_increasing_count = 1 if sorted_trades[i + 1].volume > sorted_trades[i].volume else 0
				j = i + 1
				while j < len(sorted_trades) - 1:
					q0 = float(sorted_trades[j].price)
					q1 = float(sorted_trades[j + 1].price)
					next_dir = 'up' if q1 > q0 else ('down' if q1 < q0 else 'flat')
					if next_dir != current_dir:
						break
					streak_len += 1
					if sorted_trades[j + 1].volume > sorted_trades[j].volume:
						vol_increasing_count += 1
					j += 1

				# 动量判定：连续 ≥ 3 笔同向
				if streak_len >= 3:
					vol_ratio = vol_increasing_count / streak_len
					# 置信度：基础 0.5 + 趋势长度 + 量能确认（上限 0.95）
					confidence = min(0.5 + 0.08 * (streak_len - 2) + 0.15 * vol_ratio, 0.95)
					patterns.append({
						'pattern_type': 'momentum',
						'code': code,
						'direction': current_dir,
						'streak_length': streak_len,
						'volume_confirmation': f'{vol_increasing_count}/{streak_len}',
						'description': (
							f'证券 {code} 检测到{"上涨" if current_dir == "up" else "下跌"}动量，'
							f'连续 {streak_len} 笔交易价格{"上涨" if current_dir == "up" else "下跌"}，'
							f'成交量确认 {vol_increasing_count}/{streak_len}'
						),
						'confidence': round(confidence, 2)
					})
				i = j

		# 按置信度降序排列
		patterns.sort(key=lambda p: p['confidence'], reverse=True)
		return patterns

	@staticmethod
	def _identify_seasonality_patterns (trades: List) -> List[Dict[str, Any]]:
		"""识别季节性交易模式

		按交易月份分组，找出交易最活跃的月份，
		帮助识别策略是否存在时间偏好（如月末效应、季末效应）。

		Args:
			trades: 交易记录列表

		Returns:
			季节性交易模式列表
		"""
		patterns = []

		if not trades:
			return patterns

		# 按月份统计交易次数
		trades_by_month = {}
		for trade in trades:
			if hasattr(trade, 'trade_time'):
				month = trade.trade_time.month
				if month not in trades_by_month:
					trades_by_month[month] = 0
				trades_by_month[month] += 1

		if trades_by_month:
			max_month = max(trades_by_month, key=trades_by_month.get)
			max_count = trades_by_month[max_month]

			patterns.append({
				'pattern_type': 'seasonality',
				'month': max_month,
				'trade_count': max_count,
				'description': f"第 {max_month} 月交易最活跃，共 {max_count} 次交易"
			})

		return patterns

	# =========================================================================
	# 静态私有方法 — 辅助计算
	# =========================================================================
	@staticmethod
	def _estimate_slippage_cost (trades: List) -> float:
		"""估算滑点成本

		使用简化的固定比例法：滑点 = 总交易额 × 0.1%（10 bps）。
		业界实践中，零售级别的滑点通常在 5-20 bps 范围。

		Args:
			trades: 交易记录列表

		Returns:
			float: 估算滑点成本金额
		"""
		total_trade_value = sum(
			t.price * t.volume for t in trades
			if hasattr(t, 'price') and hasattr(t, 'volume')
		)

		return total_trade_value * 0.001
