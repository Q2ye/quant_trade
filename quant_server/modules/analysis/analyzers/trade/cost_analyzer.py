#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成本分析器

负责分析交易成本，包括佣金、税费、滑点、冲击成本等。
"""

from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime, date, timedelta
import numpy as np
import pandas as pd
from scipy import stats

from core.utils.math_utils.statistic_calculator import StatisticCalculator


class CostAnalyzer:
	"""成本分析器"""

	def __init__ (self):
		"""初始化成本分析器"""
		self.stat_calc = StatisticCalculator()

	def analyze_trading_costs (
			self,
			trades: List[Dict[str, Any]],
			orders: Optional[List[Dict[str, Any]]] = None,
			market_data: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		分析交易成本

		Args:
			trades: 交易记录列表
			orders: 订单记录列表（可选）
			market_data: 市场数据（可选）

		Returns:
			交易成本分析结果
		"""
		try:
			if not trades:
				return self._empty_cost_analysis()

			# 计算显性成本
			explicit_costs = self._calculate_explicit_costs(trades)

			# 计算隐性成本
			implicit_costs = self._calculate_implicit_costs(trades, orders, market_data)

			# 成本分解
			cost_breakdown = self._calculate_cost_breakdown(explicit_costs, implicit_costs)

			# 成本效率分析
			cost_efficiency = self._analyze_cost_efficiency(trades, explicit_costs, implicit_costs)

			# 成本趋势分析
			cost_trends = self._analyze_cost_trends(trades)

			# 构建结果
			result = {
				'explicit_costs': explicit_costs,
				'implicit_costs': implicit_costs,
				'total_costs': {
					'total_explicit_cost': explicit_costs['total_cost'],
					'total_implicit_cost': implicit_costs['total_cost'],
					'total_trading_cost': explicit_costs['total_cost'] + implicit_costs['total_cost']
				},
				'cost_breakdown': cost_breakdown,
				'cost_efficiency': cost_efficiency,
				'cost_trends': cost_trends,
				'summary': self._create_cost_summary(trades, explicit_costs, implicit_costs)
			}

			return result

		except Exception as e:
			raise ValueError(f"交易成本分析失败: {str(e)}")

	def analyze_slippage (
			self,
			trades: List[Dict[str, Any]],
			orders: List[Dict[str, Any]],
			benchmark_prices: Optional[Dict[str, pd.Series]] = None
	) -> Dict[str, Any]:
		"""
		分析滑点成本

		Args:
			trades: 交易记录列表
			orders: 订单记录列表
			benchmark_prices: 基准价格数据（可选）

		Returns:
			滑点分析结果
		"""
		try:
			if not trades or not orders:
				return {'error': '交易或订单数据为空'}

			# 匹配交易和订单
			matched_trades = self._match_trades_with_orders(trades, orders)

			if not matched_trades:
				return {'error': '无法匹配交易和订单'}

			# 计算执行滑点
			execution_slippage = self._calculate_execution_slippage(matched_trades)

			# 计算机会成本滑点
			opportunity_slippage = self._calculate_opportunity_slippage(matched_trades, benchmark_prices)

			# 计算市场冲击
			market_impact = self._estimate_market_impact(matched_trades)

			# 滑点统计
			slippage_statistics = self._calculate_slippage_statistics(execution_slippage)

			# 滑点归因
			slippage_attribution = self._attribute_slippage(matched_trades)

			return {
				'execution_slippage': execution_slippage,
				'opportunity_slippage': opportunity_slippage,
				'market_impact': market_impact,
				'slippage_statistics': slippage_statistics,
				'slippage_attribution': slippage_attribution,
				'summary': self._create_slippage_summary(execution_slippage, opportunity_slippage, market_impact)
			}

		except Exception as e:
			raise ValueError(f"滑点分析失败: {str(e)}")

	def analyze_implementation_shortfall (
			self,
			orders: List[Dict[str, Any]],
			trades: List[Dict[str, Any]],
			decision_prices: Optional[Dict[str, float]] = None,
			benchmark: str = 'vwap'
	) -> Dict[str, Any]:
		"""
		分析实现缺口（Implementation Shortfall）

		Args:
			orders: 订单记录列表
			trades: 交易记录列表
			decision_prices: 决策价格（可选）
			benchmark: 基准类型 ('vwap', 'twap', 'arrival')

		Returns:
			实现缺口分析结果
		"""
		try:
			if not orders or not trades:
				return {'error': '订单或交易数据为空'}

			# 匹配订单和交易
			order_trade_map = self._map_orders_to_trades(orders, trades)

			if not order_trade_map:
				return {'error': '无法匹配订单和交易'}

			# 计算实现缺口
			shortfall_results = []
			total_shortfall = 0.0
			total_volume = 0.0

			for order_id, order_trades in order_trade_map.items():
				order = next((o for o in orders if o.get('order_id') == order_id), None)
				if not order:
					continue

				# 计算该订单的实现缺口
				order_shortfall = self._calculate_order_shortfall(order, order_trades, decision_prices, benchmark)

				shortfall_results.append({
					'order_id': order_id,
					**order_shortfall
				})

				# 累加总缺口
				total_shortfall += order_shortfall['total_shortfall_value']
				total_volume += order_shortfall['total_volume']

			# 计算加权平均实现缺口
			weighted_shortfall = total_shortfall / total_volume if total_volume > 0 else 0

			# 实现缺口分解
			shortfall_decomposition = self._decompose_shortfall(shortfall_results)

			# 实现缺口统计
			shortfall_statistics = self._calculate_shortfall_statistics(shortfall_results)

			return {
				'order_shortfalls': shortfall_results,
				'total_shortfall': total_shortfall,
				'weighted_shortfall': weighted_shortfall,
				'shortfall_decomposition': shortfall_decomposition,
				'shortfall_statistics': shortfall_statistics,
				'benchmark_type': benchmark
			}

		except Exception as e:
			raise ValueError(f"实现缺口分析失败: {str(e)}")

	def optimize_trading_costs (
			self,
			historical_trades: List[Dict[str, Any]],
			cost_parameters: Dict[str, Any],
			optimization_target: str = 'total_cost'
	) -> Dict[str, Any]:
		"""
		优化交易成本

		Args:
			historical_trades: 历史交易记录
			cost_parameters: 成本参数
			optimization_target: 优化目标 ('total_cost', 'slippage', 'impact')

		Returns:
			成本优化建议
		"""
		try:
			if not historical_trades:
				return {'error': '历史交易数据为空'}

			# 分析当前成本模式
			current_cost_patterns = self._analyze_cost_patterns(historical_trades)

			# 识别成本驱动因素
			cost_drivers = self._identify_cost_drivers(historical_trades)

			# 生成优化建议
			optimization_suggestions = self._generate_optimization_suggestions(
				current_cost_patterns, cost_drivers, cost_parameters, optimization_target
			)

			# 估计优化潜力
			optimization_potential = self._estimate_optimization_potential(
				historical_trades, optimization_suggestions
			)

			return {
				'current_cost_patterns': current_cost_patterns,
				'cost_drivers': cost_drivers,
				'optimization_suggestions': optimization_suggestions,
				'optimization_potential': optimization_potential,
				'optimization_target': optimization_target
			}

		except Exception as e:
			raise ValueError(f"交易成本优化失败: {str(e)}")

	def _empty_cost_analysis (self) -> Dict[str, Any]:
		"""返回空的成本分析结果"""
		return {
			'explicit_costs': {
				'total_commission': 0.0,
				'total_tax': 0.0,
				'total_fee': 0.0,
				'total_cost': 0.0
			},
			'implicit_costs': {
				'total_slippage': 0.0,
				'total_impact': 0.0,
				'total_opportunity': 0.0,
				'total_cost': 0.0
			},
			'total_costs': {
				'total_trading_cost': 0.0
			},
			'cost_breakdown': {},
			'cost_efficiency': {},
			'cost_trends': {},
			'summary': {}
		}

	def _calculate_explicit_costs (
			self,
			trades: List[Dict[str, Any]]
	) -> Dict[str, float]:
		"""计算显性成本"""
		total_commission = 0.0
		total_tax = 0.0
		total_fee = 0.0

		for trade in trades:
			# 佣金
			if 'commission' in trade:
				total_commission += float(trade['commission'])

			# 税费
			if 'tax' in trade:
				total_tax += float(trade['tax'])

			# 其他费用
			if 'fee' in trade:
				total_fee += float(trade['fee'])

		total_cost = total_commission + total_tax + total_fee

		return {
			'total_commission': total_commission,
			'total_tax': total_tax,
			'total_fee': total_fee,
			'total_cost': total_cost,
			'breakdown': {
				'commission_pct': total_commission / total_cost if total_cost > 0 else 0,
				'tax_pct': total_tax / total_cost if total_cost > 0 else 0,
				'fee_pct': total_fee / total_cost if total_cost > 0 else 0
			}
		}

	def _calculate_implicit_costs (
			self,
			trades: List[Dict[str, Any]],
			orders: Optional[List[Dict[str, Any]]],
			market_data: Optional[Dict[str, Any]]
	) -> Dict[str, float]:
		"""计算隐性成本"""
		# 简化实现
		total_slippage = 0.0
		total_impact = 0.0
		total_opportunity = 0.0

		for trade in trades:
			# 估计滑点成本（交易额的0.1%）
			trade_value = self._calculate_trade_value(trade)
			estimated_slippage = trade_value * 0.001
			total_slippage += estimated_slippage

			# 估计冲击成本（交易额的0.05%）
			estimated_impact = trade_value * 0.0005
			total_impact += estimated_impact

		# 估计机会成本（简化）
		total_opportunity = total_slippage * 0.5

		total_cost = total_slippage + total_impact + total_opportunity

		return {
			'total_slippage': total_slippage,
			'total_impact': total_impact,
			'total_opportunity': total_opportunity,
			'total_cost': total_cost,
			'breakdown': {
				'slippage_pct': total_slippage / total_cost if total_cost > 0 else 0,
				'impact_pct': total_impact / total_cost if total_cost > 0 else 0,
				'opportunity_pct': total_opportunity / total_cost if total_cost > 0 else 0
			}
		}

	def _calculate_cost_breakdown (
			self,
			explicit_costs: Dict[str, float],
			implicit_costs: Dict[str, float]
	) -> Dict[str, Any]:
		"""计算成本分解"""
		total_explicit = explicit_costs['total_cost']
		total_implicit = implicit_costs['total_cost']
		total_trading = total_explicit + total_implicit

		if total_trading == 0:
			return {
				'explicit_pct': 0.0,
				'implicit_pct': 0.0,
				'explicit_breakdown': explicit_costs['breakdown'],
				'implicit_breakdown': implicit_costs['breakdown']
			}

		return {
			'explicit_pct': total_explicit / total_trading,
			'implicit_pct': total_implicit / total_trading,
			'explicit_breakdown': explicit_costs['breakdown'],
			'implicit_breakdown': implicit_costs['breakdown'],
			'total_breakdown': {
				'commission_pct': explicit_costs['total_commission'] / total_trading,
				'tax_pct': explicit_costs['total_tax'] / total_trading,
				'fee_pct': explicit_costs['total_fee'] / total_trading,
				'slippage_pct': implicit_costs['total_slippage'] / total_trading,
				'impact_pct': implicit_costs['total_impact'] / total_trading,
				'opportunity_pct': implicit_costs['total_opportunity'] / total_trading
			}
		}

	def _analyze_cost_efficiency (
			self,
			trades: List[Dict[str, Any]],
			explicit_costs: Dict[str, float],
			implicit_costs: Dict[str, float]
	) -> Dict[str, float]:
		"""分析成本效率"""
		# 计算总交易额
		total_trade_value = 0.0
		total_volume = 0

		for trade in trades:
			trade_value = self._calculate_trade_value(trade)
			total_trade_value += trade_value
			total_volume += 1

		total_cost = explicit_costs['total_cost'] + implicit_costs['total_cost']

		if total_trade_value == 0:
			return {
				'cost_rate': 0.0,
				'cost_per_trade': 0.0,
				'cost_per_share': 0.0,
				'explicit_cost_rate': 0.0,
				'implicit_cost_rate': 0.0
			}

		# 计算平均交易规模
		avg_trade_size = total_trade_value / total_volume if total_volume > 0 else 0

		# 计算各种效率指标
		return {
			'cost_rate': total_cost / total_trade_value,
			'cost_per_trade': total_cost / total_volume if total_volume > 0 else 0,
			'cost_per_share': self._calculate_cost_per_share(trades, total_cost),
			'explicit_cost_rate': explicit_costs['total_cost'] / total_trade_value,
			'implicit_cost_rate': implicit_costs['total_cost'] / total_trade_value,
			'avg_trade_size': avg_trade_size,
			'cost_to_size_ratio': total_cost / avg_trade_size if avg_trade_size > 0 else 0
		}

	def _analyze_cost_trends (
			self,
			trades: List[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""分析成本趋势"""
		if not trades:
			return {'error': '交易数据为空'}

		# 按时间分组
		daily_costs = {}
		monthly_costs = {}

		for trade in trades:
			# 获取交易时间
			trade_time = trade.get('trade_time')
			if not trade_time:
				continue

			# 解析日期
			if isinstance(trade_time, str):
				trade_date = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))
			else:
				trade_date = trade_time

			# 日级别
			day_key = trade_date.strftime('%Y-%m-%d')
			if day_key not in daily_costs:
				daily_costs[day_key] = {'cost': 0.0, 'value': 0.0, 'count': 0}

			trade_value = self._calculate_trade_value(trade)
			trade_cost = self._estimate_trade_cost(trade)

			daily_costs[day_key]['cost'] += trade_cost
			daily_costs[day_key]['value'] += trade_value
			daily_costs[day_key]['count'] += 1

			# 月级别
			month_key = trade_date.strftime('%Y-%m')
			if month_key not in monthly_costs:
				monthly_costs[month_key] = {'cost': 0.0, 'value': 0.0, 'count': 0}

			monthly_costs[month_key]['cost'] += trade_cost
			monthly_costs[month_key]['value'] += trade_value
			monthly_costs[month_key]['count'] += 1

		# 计算成本率趋势
		daily_trends = []
		for day_key, data in daily_costs.items():
			if data['value'] > 0:
				cost_rate = data['cost'] / data['value']
				daily_trends.append({
					'date': day_key,
					'cost_rate': cost_rate,
					'avg_trade_cost': data['cost'] / data['count'] if data['count'] > 0 else 0,
					'trade_count': data['count']
				})

		monthly_trends = []
		for month_key, data in monthly_costs.items():
			if data['value'] > 0:
				cost_rate = data['cost'] / data['value']
				monthly_trends.append({
					'month': month_key,
					'cost_rate': cost_rate,
					'total_cost': data['cost'],
					'trade_count': data['count']
				})

		# 趋势分析
		trend_analysis = self._perform_trend_analysis(daily_trends)

		return {
			'daily_trends': daily_trends,
			'monthly_trends': monthly_trends,
			'trend_analysis': trend_analysis,
			'summary': {
				'total_days': len(daily_costs),
				'total_months': len(monthly_costs),
				'avg_daily_cost_rate': np.mean([t['cost_rate'] for t in daily_trends]) if daily_trends else 0
			}
		}

	def _create_cost_summary (
			self,
			trades: List[Dict[str, Any]],
			explicit_costs: Dict[str, float],
			implicit_costs: Dict[str, float]
	) -> Dict[str, Any]:
		"""创建成本摘要"""
		total_trade_value = sum(self._calculate_trade_value(t) for t in trades)
		total_volume = len(trades)

		total_cost = explicit_costs['total_cost'] + implicit_costs['total_cost']

		return {
			'total_trades': total_volume,
			'total_trade_value': total_trade_value,
			'total_explicit_cost': explicit_costs['total_cost'],
			'total_implicit_cost': implicit_costs['total_cost'],
			'total_trading_cost': total_cost,
			'overall_cost_rate': total_cost / total_trade_value if total_trade_value > 0 else 0,
			'avg_cost_per_trade': total_cost / total_volume if total_volume > 0 else 0,
			'main_cost_driver': self._identify_main_cost_driver(explicit_costs, implicit_costs)
		}

	def _calculate_trade_value (
			self,
			trade: Dict[str, Any]
	) -> float:
		"""计算交易金额"""
		price = trade.get('price', 0)
		volume = trade.get('volume', 0)
		return float(price * volume)

	def _estimate_trade_cost (
			self,
			trade: Dict[str, Any]
	) -> float:
		"""估计单笔交易成本"""
		trade_value = self._calculate_trade_value(trade)

		# 显性成本
		explicit_cost = 0.0
		if 'commission' in trade:
			explicit_cost += float(trade['commission'])
		if 'tax' in trade:
			explicit_cost += float(trade['tax'])
		if 'fee' in trade:
			explicit_cost += float(trade['fee'])

		# 隐性成本（估计为交易额的0.15%）
		implicit_cost = trade_value * 0.0015

		return explicit_cost + implicit_cost

	def _calculate_cost_per_share (
			self,
			trades: List[Dict[str, Any]],
			total_cost: float
	) -> float:
		"""计算每股成本"""
		total_shares = 0

		for trade in trades:
			volume = trade.get('volume', 0)
			total_shares += volume

		if total_shares == 0:
			return 0.0

		return total_cost / total_shares

	def _perform_trend_analysis (
			self,
			daily_trends: List[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""执行趋势分析"""
		if len(daily_trends) < 5:
			return {'insufficient_data': True}

		# 提取成本率序列
		cost_rates = [t['cost_rate'] for t in daily_trends]

		# 计算趋势线（线性回归）
		x = np.arange(len(cost_rates))
		y = np.array(cost_rates)

		try:
			slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

			# 计算移动平均
			window = min(10, len(cost_rates))
			ma = pd.Series(cost_rates).rolling(window=window, center=True).mean()

			# 识别异常点
			z_scores = np.abs(stats.zscore(cost_rates))
			outliers = np.where(z_scores > 2)[0]

			return {
				'trend_slope': float(slope),
				'trend_intercept': float(intercept),
				'trend_r_squared': float(r_value ** 2),
				'trend_p_value': float(p_value),
				'moving_average': ma.tolist(),
				'outlier_indices': outliers.tolist(),
				'avg_cost_rate': float(np.mean(cost_rates)),
				'std_cost_rate': float(np.std(cost_rates)),
				'trend_direction': 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable'
			}

		except Exception as e:
			return {'trend_analysis_error': str(e)}

	def _identify_main_cost_driver (
			self,
			explicit_costs: Dict[str, float],
			implicit_costs: Dict[str, float]
	) -> str:
		"""识别主要成本驱动因素"""
		costs = {
			'commission': explicit_costs['total_commission'],
			'tax': explicit_costs['total_tax'],
			'fee': explicit_costs['total_fee'],
			'slippage': implicit_costs['total_slippage'],
			'impact': implicit_costs['total_impact'],
			'opportunity': implicit_costs['total_opportunity']
		}

		if not costs:
			return 'unknown'

		main_driver = max(costs.items(), key=lambda x: x[1])
		return main_driver[0]