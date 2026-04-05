"""
持仓处理器模块
负责持仓相关的计算和处理
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Optional, Any

from ....shared.utils.validation import validate_position_data

logger = logging.getLogger(__name__)


class PositionProcessor:
	"""
	持仓处理器
	负责持仓相关的计算、分析和处理
	"""

	def __init__ (self):
		"""初始化持仓处理器"""

	@staticmethod
	def calculate_position_pnl (
			position: Dict,
			current_price: float,
			include_fees: bool = True
	) -> Dict[str, float]:
		"""
		计算持仓盈亏

		Args:
			position: 持仓信息
			current_price: 当前价格
			include_fees: 是否包含费用

		Returns:
			Dict: 盈亏计算结果
		"""
		try:
			# 验证持仓数据
			PositionProcessor._validate_position(position)

			# 获取持仓数据
			quantity = float(position.get('current_quantity', 0))
			cost_price = float(position.get('cost_price', 0))

			if quantity == 0 or cost_price == 0:
				return {
					'unrealized_pnl': 0.0,
					'unrealized_pnl_rate': 0.0,
					'market_value': 0.0,
					'cost_value': 0.0
				}

			# 计算持仓价值
			cost_value = quantity * cost_price
			market_value = quantity * current_price

			# 计算浮动盈亏
			unrealized_pnl = market_value - cost_value
			unrealized_pnl_rate = unrealized_pnl / cost_value if cost_value != 0 else 0.0

			# 如果包含费用，调整盈亏
			if include_fees:
				# 计算预计卖出费用（佣金+印花税）
				sell_fee = PositionProcessor._calculate_sell_fee(market_value)
				unrealized_pnl -= sell_fee

			# 返回计算结果
			return {
				'unrealized_pnl': float(unrealized_pnl),
				'unrealized_pnl_rate': float(unrealized_pnl_rate),
				'market_value': float(market_value),
				'cost_value': float(cost_value),
				'current_price': float(current_price),
				'quantity': float(quantity),
				'cost_price': float(cost_price)
			}

		except Exception as e:
			logger.error(f"计算持仓盈亏失败: {str(e)}", exc_info=True)
			raise

	@staticmethod
	def calculate_position_cost (
			trades: List[Dict],
			current_quantity: float = 0,
			current_cost: float = 0
	) -> Dict[str, float]:
		"""
		计算持仓成本（先进先出法）

		Args:
			trades: 交易记录列表
			current_quantity: 当前持仓数量
			current_cost: 当前持仓成本

		Returns:
			Dict: 成本计算结果
		"""
		try:
			if not trades:
				return {
					'avg_cost': 0.0,
					'total_cost': 0.0,
					'remaining_quantity': current_quantity,
					'remaining_cost': current_cost
				}

			# 按交易时间排序
			sorted_trades = sorted(trades, key=lambda x: x.get('trade_time', datetime.min))

			# 使用队列模拟先进先出
			fifo_queue = []

			for trade in sorted_trades:
				direction = trade.get('direction')  # 'buy' or 'sell'
				quantity = float(trade.get('quantity', 0))
				price = float(trade.get('price', 0))
				trade_id = trade.get('trade_id')

				if direction == 'buy':
					# 买入：加入队列
					fifo_queue.append({
						'trade_id': trade_id,
						'quantity': quantity,
						'price': price,
						'remaining': quantity
					})
				elif direction == 'sell':
					# 卖出：从队列中扣除
					remaining_sell = quantity

					while remaining_sell > 0 and fifo_queue:
						first_buy = fifo_queue[0]

						if first_buy['remaining'] <= remaining_sell:
							# 完全卖出这批买入
							remaining_sell -= first_buy['remaining']
							fifo_queue.pop(0)
						else:
							# 部分卖出这批买入
							first_buy['remaining'] -= remaining_sell
							remaining_sell = 0

			# 计算剩余持仓的平均成本
			total_quantity = 0
			total_cost = 0

			for item in fifo_queue:
				total_quantity += item['remaining']
				total_cost += item['remaining'] * item['price']

			# 加上当前持仓
			total_quantity += current_quantity
			total_cost += current_cost

			avg_cost = total_cost / total_quantity if total_quantity > 0 else 0

			return {
				'avg_cost': float(avg_cost),
				'total_cost': float(total_cost),
				'total_quantity': float(total_quantity),
				'remaining_trades': len(fifo_queue),
				'fifo_queue': fifo_queue
			}

		except Exception as e:
			logger.error(f"计算持仓成本失败: {str(e)}", exc_info=True)
			raise

	@staticmethod
	def calculate_position_exposure (
			positions: List[Dict],
			total_asset: float,
			risk_factors: Optional[Dict] = None
	) -> Dict[str, Any]:
		"""
		计算持仓风险敞口

		Args:
			positions: 持仓列表
			total_asset: 总资产
			risk_factors: 风险因子

		Returns:
			Dict: 风险敞口计算结果
		"""
		try:
			if not positions or total_asset <= 0:
				return {
					'total_exposure': 0.0,
					'sector_exposure': {},
					'concentration_risk': 0.0,
					'var_95': 0.0,
					'expected_shortfall': 0.0
				}

			# 计算总敞口
			total_market_value = sum(p.get('market_value', 0) for p in positions)
			total_exposure = total_market_value / total_asset if total_asset > 0 else 0

			# 按行业计算敞口
			sector_exposure = PositionProcessor._calculate_sector_exposure(positions, total_asset)

			# 计算集中度风险（赫芬达尔指数）
			concentration_risk = PositionProcessor._calculate_concentration_risk(positions, total_asset)

			# 计算在险价值（VaR）
			var_95 = PositionProcessor._calculate_var_95(positions, risk_factors)

			# 计算预期缺口（Expected Shortfall）
			expected_shortfall = PositionProcessor._calculate_expected_shortfall(positions, risk_factors)

			return {
				'total_exposure': float(total_exposure),
				'sector_exposure': sector_exposure,
				'concentration_risk': float(concentration_risk),
				'var_95': float(var_95),
				'expected_shortfall': float(expected_shortfall),
				'total_market_value': float(total_market_value)
			}

		except Exception as e:
			logger.error(f"计算风险敞口失败: {str(e)}", exc_info=True)
			raise

	@staticmethod
	def analyze_position_performance (
			position_history: List[Dict],
			benchmark_history: Optional[List[Dict]] = None
	) -> Dict[str, Any]:
		"""
		分析持仓绩效

		Args:
			position_history: 持仓历史
			benchmark_history: 基准历史

		Returns:
			Dict: 绩效分析结果
		"""
		try:
			if not position_history:
				return {
					'total_return': 0.0,
					'annualized_return': 0.0,
					'volatility': 0.0,
					'sharpe_ratio': 0.0,
					'max_drawdown': 0.0,
					'beta': 0.0,
					'alpha': 0.0
				}

			# 准备数据
			dates = []
			returns = []
			values = []

			for record in position_history:
				dates.append(record.get('date'))
				values.append(float(record.get('market_value', 0)))

				if len(values) > 1:
					ret = (values[-1] - values[-2]) / values[-2] if values[-2] != 0 else 0
					returns.append(ret)

			# 计算绩效指标
			if len(returns) == 0:
				return {
					'total_return': 0.0,
					'annualized_return': 0.0,
					'volatility': 0.0,
					'sharpe_ratio': 0.0,
					'max_drawdown': 0.0,
					'beta': 0.0,
					'alpha': 0.0
				}

			# 计算总收益
			if len(values) >= 2:
				total_return = (values[-1] - values[0]) / values[0] if values[0] != 0 else 0
			else:
				total_return = 0

			# 计算年化收益（假设每日数据）
			annualized_return = PositionProcessor._calculate_annualized_return(returns, period='daily')

			# 计算波动率
			volatility = PositionProcessor._calculate_volatility(returns, annualize=True)

			# 计算夏普比率（假设无风险利率为0.03）
			sharpe_ratio = PositionProcessor._calculate_sharpe_ratio(returns, risk_free_rate=0.03)

			# 计算最大回撤
			max_drawdown = PositionProcessor._calculate_max_drawdown(values)

			# 计算Beta和Alpha（如果有基准）
			beta = 0.0
			alpha = 0.0

			if benchmark_history and len(benchmark_history) == len(returns):
				benchmark_returns = [
					float(r.get('return', 0)) for r in benchmark_history[-len(returns):]
				]

				beta = PositionProcessor._calculate_beta(returns, benchmark_returns)
				alpha = PositionProcessor._calculate_alpha(
					returns, benchmark_returns, risk_free_rate=0.03
				)

			return {
				'total_return': float(total_return),
				'annualized_return': float(annualized_return),
				'volatility': float(volatility),
				'sharpe_ratio': float(sharpe_ratio),
				'max_drawdown': float(max_drawdown),
				'beta': float(beta),
				'alpha': float(alpha),
				'return_series': returns,
				'value_series': values,
				'analysis_period': {
					'start_date': dates[0] if dates else None,
					'end_date': dates[-1] if dates else None,
					'days': len(dates)
				}
			}

		except Exception as e:
			logger.error(f"分析持仓绩效失败: {str(e)}", exc_info=True)
			raise

	@staticmethod
	def optimize_position_sizing (
			positions: List[Dict],
			total_capital: float,
			risk_constraints: Dict[str, float],
			optimization_method: str = 'equal_risk'
	) -> Dict[str, Any]:
		"""
		优化持仓头寸规模

		Args:
			positions: 当前持仓
			total_capital: 总资本
			risk_constraints: 风险约束
			optimization_method: 优化方法

		Returns:
			Dict: 优化结果
		"""
		try:
			if not positions or total_capital <= 0:
				return {}

			# 计算当前头寸
			current_sizes = {}
			for pos in positions:
				security_id = pos.get('security_id')
				current_value = pos.get('market_value', 0)
				current_sizes[security_id] = float(current_value)

			# 根据优化方法计算目标头寸
			if optimization_method == 'equal_risk':
				target_sizes = PositionProcessor._equal_risk_sizing(
					positions, total_capital, risk_constraints
				)
			elif optimization_method == 'kelly_criterion':
				target_sizes = PositionProcessor._kelly_criterion_sizing(
					positions, total_capital, risk_constraints
				)
			elif optimization_method == 'mean_variance':
				target_sizes = PositionProcessor._mean_variance_sizing(
					positions, total_capital, risk_constraints
				)
			else:
				# 默认等权重
				target_sizes = PositionProcessor._equal_weight_sizing(positions, total_capital)

			# 计算调整建议
			adjustments = {}
			total_target_value = sum(target_sizes.values())

			for security_id, target_value in target_sizes.items():
				current_value = current_sizes.get(security_id, 0)

				# 计算调整金额
				adjustment = target_value - current_value

				# 计算调整权重
				if total_target_value > 0:
					target_weight = target_value / total_target_value
				else:
					target_weight = 0

				adjustments[security_id] = {
					'current_value': float(current_value),
					'target_value': float(target_value),
					'adjustment': float(adjustment),
					'current_weight': float(current_value / total_capital) if total_capital > 0 else 0,
					'target_weight': float(target_weight),
					'adjustment_pct': float(adjustment / total_capital) if total_capital > 0 else 0
				}

			return {
				'optimization_method': optimization_method,
				'total_capital': float(total_capital),
				'target_total_value': float(total_target_value),
				'adjustments': adjustments,
				'constraints': risk_constraints
			}

		except Exception as e:
			logger.error(f"优化头寸规模失败: {str(e)}", exc_info=True)
			raise

	@staticmethod
	def _validate_position (position: Dict) -> bool:
		"""
		验证持仓数据

		Args:
			position: 持仓数据

		Returns:
			bool: 是否有效
		"""
		required_fields = ['security_id', 'current_quantity']

		for field in required_fields:
			if field not in position:
				raise ValueError(f"持仓数据缺少必需字段: {field}")

		# 使用共享验证工具
		validate_position_data(position)

		return True

	@staticmethod
	def _calculate_sell_fee (market_value: float) -> float:
		"""
		计算卖出费用

		Args:
			market_value: 市值

		Returns:
			float: 预计卖出费用
		"""
		# 佣金：万3，最低5元
		commission = max(market_value * 0.0003, 5)

		# 印花税：千1
		stamp_tax = market_value * 0.001

		# 过户费：万0.2
		transfer_fee = market_value * 0.00002

		return commission + stamp_tax + transfer_fee

	@staticmethod
	def _calculate_sector_exposure (
			positions: List[Dict],
			total_asset: float
	) -> Dict[str, float]:
		"""计算行业敞口"""
		sector_exposure = {}

		for pos in positions:
			sector = pos.get('sector', '未知')
			market_value = pos.get('market_value', 0)

			if sector not in sector_exposure:
				sector_exposure[sector] = 0

			sector_exposure[sector] += market_value

		# 转换为百分比
		for sector in sector_exposure:
			sector_exposure[sector] = float(sector_exposure[sector] / total_asset) if total_asset > 0 else 0

		return sector_exposure

	@staticmethod
	def _calculate_concentration_risk (
			positions: List[Dict],
			total_asset: float
	) -> float:
		"""计算集中度风险（赫芬达尔指数）"""
		if total_asset <= 0:
			return 0.0

		weights = []
		for pos in positions:
			market_value = pos.get('market_value', 0)
			weight = market_value / total_asset
			weights.append(weight)

		# 赫芬达尔指数
		hhi = sum(w * w for w in weights)
		return float(hhi)

	@staticmethod
	def _calculate_var_95 (
			positions: List[Dict],
			_risk_factors: Optional[Dict]
	) -> float:
		"""计算95%置信度的在险价值"""
		# 简化的VaR计算
		# 实际实现中应该使用历史模拟法或蒙特卡洛模拟

		total_value = sum(p.get('market_value', 0) for p in positions)

		# 假设波动率为20%
		volatility = 0.20
		# 95%置信度对应的Z值为1.645
		z_score = 1.645

		var_95 = total_value * volatility * z_score
		return float(var_95)

	@staticmethod
	def _calculate_expected_shortfall (
			positions: List[Dict],
			_risk_factors: Optional[Dict]
	) -> float:
		"""计算预期缺口"""
		# 简化的ES计算（CVaR）
		# 假设损失分布为正态分布

		var_95 = PositionProcessor._calculate_var_95(positions, _risk_factors)

		# 正态分布下，95% VaR对应的ES约为1.75倍VaR
		return float(var_95 * 1.75)

	@staticmethod
	def _equal_weight_sizing (
			positions: List[Dict],
			total_capital: float
	) -> Dict[str, float]:
		"""等权重头寸分配"""
		n_positions = len(positions)
		if n_positions == 0:
			return {}

		equal_weight = 1.0 / n_positions
		target_value = total_capital * equal_weight

		target_sizes = {}
		for pos in positions:
			security_id = pos.get('security_id')
			target_sizes[security_id] = target_value

		return target_sizes

	@staticmethod
	def _equal_risk_sizing (
			positions: List[Dict],
			total_capital: float,
			risk_constraints: Dict[str, float]
	) -> Dict[str, float]:
		"""等风险贡献头寸分配"""
		# 简化的风险平价模型
		# 实际实现中需要更复杂的风险模型

		n_positions = len(positions)
		if n_positions == 0:
			return {}

		# 假设每个持仓有相同的风险贡献
		target_sizes = {}

		for pos in positions:
			security_id = pos.get('security_id')
			# 简化：假设波动率为20%
			volatility = 0.20
			# 等风险贡献：头寸与波动率成反比
			target_weight = 1 / volatility
			target_sizes[security_id] = total_capital * target_weight / sum(1 / 0.20 for _ in positions)

		return target_sizes

	@staticmethod
	def _kelly_criterion_sizing (
			positions: List[Dict],
			total_capital: float,
			risk_constraints: Dict[str, float]
	) -> Dict[str, float]:
		"""凯利公式头寸分配"""
		# 凯利公式：f = (bp - q) / b
		# 其中：b = 赔率，p = 胜率，q = 败率

		target_sizes = {}

		for pos in positions:
			security_id = pos.get('security_id')

			# 简化：假设胜率55%，赔率2:1
			win_rate = 0.55
			odds = 2.0  # 赔率

			# 凯利比例
			kelly_fraction = (odds * win_rate - (1 - win_rate)) / odds

			# 应用约束（如最大仓位限制）
			max_position = risk_constraints.get('max_position_pct', 0.1)
			kelly_fraction = min(kelly_fraction, max_position)

			target_sizes[security_id] = total_capital * kelly_fraction

		return target_sizes

	@staticmethod
	def _mean_variance_sizing (
			positions: List[Dict],
			total_capital: float,
			risk_constraints: Dict[str, float]
	) -> Dict[str, float]:
		"""均值-方差优化头寸分配"""
		# 简化的马科维茨投资组合优化

		n_positions = len(positions)
		if n_positions == 0:
			return {}

		# 假设期望收益和协方差矩阵
		# 实际实现中需要估计这些参数

		# 等权重作为初始解
		return PositionProcessor._equal_weight_sizing(positions, total_capital)

	@staticmethod
	def _calculate_annualized_return (returns: List[float], period: str = 'daily') -> float:
		"""计算年化收益"""
		if not returns:
			return 0.0
		total_return = (1 + sum(returns)) - 1
		n_periods = len(returns)
		if period == 'daily':
			days_in_year = 252
			return (1 + total_return) ** (days_in_year / n_periods) - 1
		return total_return

	@staticmethod
	def _calculate_volatility (returns: List[float], annualize: bool = True) -> float:
		"""计算波动率"""
		if not returns or len(returns) < 2:
			return 0.0
		mean_return = sum(returns) / len(returns)
		variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
		volatility = math.sqrt(variance)
		if annualize:
			volatility *= math.sqrt(252)
		return volatility

	@staticmethod
	def _calculate_sharpe_ratio (returns: List[float], risk_free_rate: float = 0.03) -> float:
		"""计算夏普比率"""
		if not returns:
			return 0.0
		annualized_return = PositionProcessor._calculate_annualized_return(returns)
		volatility = PositionProcessor._calculate_volatility(returns, annualize=True)
		if volatility == 0:
			return 0.0
		return (annualized_return - risk_free_rate) / volatility

	@staticmethod
	def _calculate_max_drawdown (values: List[float]) -> float:
		"""计算最大回撤"""
		if not values or len(values) < 2:
			return 0.0
		max_drawdown = 0.0
		peak = values[0]
		for value in values[1:]:
			if value > peak:
				peak = value
			drawdown = (peak - value) / peak
			if drawdown > max_drawdown:
				max_drawdown = drawdown
		return max_drawdown

	@staticmethod
	def _calculate_beta (returns: List[float], benchmark_returns: List[float]) -> float:
		"""计算Beta"""
		if not returns or not benchmark_returns or len(returns) != len(benchmark_returns):
			return 0.0
		mean_return = sum(returns) / len(returns)
		mean_benchmark = sum(benchmark_returns) / len(benchmark_returns)
		covariance = sum((r - mean_return) * (b - mean_benchmark) for r, b in zip(returns, benchmark_returns)) / (len(returns) - 1)
		benchmark_variance = sum((b - mean_benchmark) ** 2 for b in benchmark_returns) / (len(benchmark_returns) - 1)
		if benchmark_variance == 0:
			return 0.0
		return covariance / benchmark_variance

	@staticmethod
	def _calculate_alpha (returns: List[float], benchmark_returns: List[float], risk_free_rate: float = 0.03) -> float:
		"""计算Alpha"""
		if not returns or not benchmark_returns:
			return 0.0
		beta = PositionProcessor._calculate_beta(returns, benchmark_returns)
		annualized_return = PositionProcessor._calculate_annualized_return(returns)
		annualized_benchmark = PositionProcessor._calculate_annualized_return(benchmark_returns)
		return annualized_return - (risk_free_rate + beta * (annualized_benchmark - risk_free_rate))


# 工具函数
def calculate_position_pnl (
		position: Dict,
		current_price: float,
		include_fees: bool = True
) -> Dict[str, float]:
	"""计算持仓盈亏（快捷函数）"""
	return PositionProcessor.calculate_position_pnl(position, current_price, include_fees)


def calculate_position_cost (
		trades: List[Dict],
		current_quantity: float = 0,
		current_cost: float = 0
) -> Dict[str, float]:
	"""计算持仓成本（快捷函数）"""
	return PositionProcessor.calculate_position_cost(trades, current_quantity, current_cost)


def calculate_position_exposure (
		positions: List[Dict],
		total_asset: float,
		risk_factors: Optional[Dict] = None
) -> Dict[str, Any]:
	"""计算持仓风险敞口（快捷函数）"""
	return PositionProcessor.calculate_position_exposure(positions, total_asset, risk_factors)