#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
成本分析器

负责分析交易成本，包括佣金、税费、滑点、冲击成本等。
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
from scipy import stats


class CostAnalyzer:
	"""成本分析器"""

	def __init__ (self):
		"""初始化成本分析器"""

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

	@staticmethod
	def _empty_cost_analysis () -> Dict[str, Any]:
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

	@staticmethod
	def _calculate_explicit_costs (
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

	@staticmethod
	def _calculate_implicit_costs (
			trades: List[Dict[str, Any]],
			orders: Optional[List[Dict[str, Any]]] = None,
			market_data: Optional[Dict[str, Any]] = None
		) -> Dict[str, float]:
		"""计算隐性成本"""
		_ = orders
		_ = market_data
		total_slippage = 0.0
		total_impact = 0.0

		for trade in trades:
			trade_value = CostAnalyzer._calculate_trade_value(trade)
			estimated_slippage = trade_value * 0.001
			total_slippage += estimated_slippage

			estimated_impact = trade_value * 0.0005
			total_impact += estimated_impact

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

	@staticmethod
	def _calculate_cost_breakdown (
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

	@staticmethod
	def _calculate_trade_value (
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

	@staticmethod
	def _calculate_cost_per_share (
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

	@staticmethod
	def _perform_trend_analysis (
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

	@staticmethod
	def _identify_main_cost_driver (
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

	@staticmethod
	def _match_trades_with_orders (
			trades: List[Dict[str, Any]],
			orders: List[Dict[str, Any]]
		) -> List[Dict[str, Any]]:
		"""匹配交易和订单"""
		matched = []
		order_map = {o.get('order_id', ''): o for o in orders if o.get('order_id')}
		symbol_orders: Dict[str, List[Dict]] = {}
		for o in orders:
			sym = o.get('symbol', o.get('ts_code', ''))
			symbol_orders.setdefault(sym, []).append(o)

		for trade in trades:
			match = {'trade': trade, 'order': None, 'match_method': 'none'}
			oid = trade.get('order_id', '')
			if oid and oid in order_map:
				match['order'] = order_map[oid]
				match['match_method'] = 'order_id'
			else:
				sym = trade.get('symbol', trade.get('ts_code', ''))
				candidates = symbol_orders.get(sym, [])
				if candidates:
					match['order'] = candidates[0]
					match['match_method'] = 'symbol'
			matched.append(match)
		return matched

	@staticmethod
	def _calculate_execution_slippage (
			matched_trades: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""计算执行滑点"""
		slippages = []
		total_value = 0.0
		total_volume = 0

		for match in matched_trades:
			trade = match['trade']
			order = match.get('order')
			exec_price = float(trade.get('price', 0))
			volume = int(trade.get('volume', 0))
			direction = trade.get('direction', order.get('direction', 'buy') if order else 'buy')
			target_price = float(order.get('price', order.get('limit_price', 0))) if order else 0.0

			if target_price > 0 and exec_price > 0:
				if direction in ('buy', 'BUY'):
					slippage_bps = (exec_price - target_price) / target_price * 10000
				else:
					slippage_bps = (target_price - exec_price) / target_price * 10000
				sv = abs(exec_price - target_price) * volume
				total_value += sv
				total_volume += volume
				slippages.append({
					'trade_id': trade.get('trade_id', ''),
					'order_id': order.get('order_id', '') if order else '',
					'exec_price': exec_price, 'target_price': target_price,
					'slippage_bps': slippage_bps, 'slippage_value': sv,
					'volume': volume, 'direction': direction
				})

		avg_price = sum(s['exec_price'] for s in slippages) / len(slippages) if slippages else 0
		return {
			'slippages': slippages,
			'total_slippage_value': total_value,
			'total_volume': total_volume,
			'avg_slippage_bps': total_value / (
						total_volume * avg_price) * 10000 if slippages and total_volume > 0 else 0,
			'matched_count': len(slippages)
		}

	@staticmethod
	def _calculate_opportunity_slippage (
			matched_trades: List[Dict[str, Any]],
			benchmark_prices: Optional[Dict[str, pd.Series]] = None
		) -> Dict[str, Any]:
		"""计算机会成本滑点"""
		_ = benchmark_prices
		costs = []
		total = 0.0
		for match in matched_trades:
			trade = match['trade']
			order = match.get('order')
			if not order:
				continue
			ov = int(order.get('volume', order.get('quantity', 0)))
			tv = int(trade.get('volume', 0))
			unfilled = ov - tv
			if unfilled > 0:
				exec_price = float(trade.get('price', 0))
				estimated_move = exec_price * 0.005
				opp = unfilled * estimated_move
				total += opp
				costs.append({
					'order_id': order.get('order_id', ''),
					'unfilled_volume': unfilled,
					'estimated_opportunity': opp,
					'fill_rate': tv / ov if ov > 0 else 1.0
				})
		return {'opportunity_costs': costs, 'total_opportunity_cost': total, 'unfilled_orders': len(costs)}

	@staticmethod
	def _estimate_market_impact (
			matched_trades: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""估计市场冲击成本 — Almgren-Chriss 模型 (square-root law: eta * sigma * Q^beta)"""
		if not matched_trades:
			return {'impacts': [], 'total_market_impact': 0, 'avg_impact_bps': 0}

		# Group trades by symbol and compute per-symbol statistics
		symbol_groups: Dict[str, List[dict]] = {}
		symbol_volumes: Dict[str, List[float]] = {}
		symbol_prices: Dict[str, List[float]] = {}

		for match in matched_trades:
			trade = match['trade']
			sym = trade.get('ts_code', trade.get('symbol', ''))
			vol = int(trade.get('volume', 0))
			px = float(trade.get('price', 0))
			if sym and vol > 0 and px > 0:
				symbol_groups.setdefault(sym, []).append(match)
				symbol_volumes.setdefault(sym, []).append(float(vol))
				symbol_prices.setdefault(sym, []).append(px)

		# Pre-compute per-symbol median volume and price volatility
		symbol_stats = {}
		for sym in symbol_groups:
			vols = np.array(symbol_volumes[sym])
			prices = np.array(symbol_prices[sym])
			median_vol = float(np.median(vols))
			if len(prices) >= 2:
				est_vol = float(np.std(prices, ddof=1) / np.mean(prices))
			else:
				est_vol = 0.02  # Default daily vol 2%
			symbol_stats[sym] = {'median_vol': median_vol, 'est_volatility': max(est_vol, 0.001)}

		impacts = []
		total = 0.0

		for match in matched_trades:
			trade = match['trade']
			volume = int(trade.get('volume', 0))
			price = float(trade.get('price', 0))
			tv = price * volume

			if volume == 0 or price == 0:
				impacts.append({'trade_id': trade.get('trade_id', ''),
					'estimated_impact_bps': 0, 'estimated_impact_value': 0,
					'trade_value': 0})
				continue

			sym = trade.get('ts_code', trade.get('symbol', ''))
			aStats = symbol_stats.get(sym, {'median_vol': float(volume), 'est_volatility': 0.02})

			# Participation rate: trade volume relative to median for this symbol
			relative_size = volume / aStats['median_vol'] if aStats['median_vol'] > 0 else 1.0
			est_participation = min(relative_size * 0.05, 0.20)

			# Almgren-Chriss square-root impact: eta * sigma * (participation)^beta
			eta = 0.1
			beta = 0.5
			impact_frac = eta * stats['est_volatility'] * (est_participation ** beta)
			impact_bps = impact_frac * 10000

			iv = tv * impact_frac
			total += iv
			impacts.append({
				'trade_id': trade.get('trade_id', ''),
				'ts_code': sym,
				'estimated_impact_bps': round(impact_bps, 4),
				'estimated_impact_value': round(iv, 4),
				'trade_value': tv,
				'est_participation': round(est_participation, 4),
				'est_volatility': round(aStats['est_volatility'], 6)
			})

		total_tv = sum(i['trade_value'] for i in impacts)
		return {
			'impacts': impacts,
			'total_market_impact': round(total, 4),
			'avg_impact_bps': round(total / total_tv * 10000, 4) if total_tv > 0 else 0
		}

	@staticmethod
	def _calculate_slippage_statistics (
			execution_slippage: Dict[str, Any]
		) -> Dict[str, Any]:
		"""计算滑点统计"""
		slippages = execution_slippage.get('slippages', [])
		if not slippages:
			return {'count': 0}
		vals = np.array([s['slippage_bps'] for s in slippages if 'slippage_bps' in s])
		costs = np.array([s['slippage_value'] for s in slippages if 'slippage_value' in s])
		if len(vals) == 0:
			return {'count': len(slippages)}
		return {
			'count': len(vals),
			'mean_bps': float(np.mean(vals)), 'median_bps': float(np.median(vals)),
			'std_bps': float(np.std(vals)), 'min_bps': float(np.min(vals)),
			'max_bps': float(np.max(vals)), 'percentile_95_bps': float(np.percentile(vals, 95)),
			'total_cost': float(np.sum(costs)) if len(costs) > 0 else 0.0,
			'positive_slippage_pct': float(np.sum(vals > 0) / len(vals) * 100)
		}

	@staticmethod
	def _attribute_slippage (
			matched_trades: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""滑点归因分析"""
		attr = {'spread_cost': 0.0, 'delay_cost': 0.0, 'price_impact': 0.0, 'timing_cost': 0.0}
		for match in matched_trades:
			trade = match['trade']
			tv = float(trade.get('price', 0)) * int(trade.get('volume', 0))
			attr['spread_cost'] += tv * 0.0002
			attr['delay_cost'] += tv * 0.0003
			attr['price_impact'] += tv * 0.0005
			attr['timing_cost'] += tv * 0.0004
		total = sum(attr.values())
		result = {**attr, 'total': total}
		if total > 0:
			for k in ['spread_cost', 'delay_cost', 'price_impact', 'timing_cost']:
				result[k.replace('_cost', '_pct')] = int(attr[k] / total * 100)
		return result

	@staticmethod
	def _create_slippage_summary (
			execution_slippage: Dict[str, Any],
			opportunity_slippage: Dict[str, Any],
			market_impact: Dict[str, Any]
		) -> Dict[str, Any]:
		"""创建滑点分析摘要"""
		te = execution_slippage.get('total_slippage_value', 0.0)
		to = opportunity_slippage.get('total_opportunity_cost', 0.0)
		ti = market_impact.get('total_market_impact', 0.0)
		total = te + to + ti
		main = max((te, 'execution_slippage'), (to, 'opportunity_cost'), (ti, 'market_impact'), key=lambda x: x[0])
		return {
			'total_slippage_cost': total,
			'execution_slippage': te, 'opportunity_cost': to, 'market_impact': ti,
			'main_component': main[1]
		}

	# ---- Implementation Shortfall helpers ----

	@staticmethod
	def _map_orders_to_trades (
			orders: List[Dict[str, Any]],
			trades: List[Dict[str, Any]]
		) -> Dict[str, List[Dict[str, Any]]]:
		"""将订单映射到交易"""
		otm: Dict[str, List[Dict[str, Any]]] = {}
		for trade in trades:
			oid = trade.get('order_id', '')
			otm.setdefault(oid, []).append(trade) if oid else None
		for order in orders:
			oid = order.get('order_id', '')
			if oid and oid not in otm:
				otm[oid] = []
		return otm

	@staticmethod
	def _calculate_order_shortfall (
			order: Dict[str, Any],
			order_trades: List[Dict[str, Any]],
			decision_prices: Optional[Dict[str, float]] = None,
			benchmark: str = 'vwap'
		) -> Dict[str, Any]:
		"""计算单个订单的实现缺口"""
		_ = benchmark
		symbol = order.get('symbol', order.get('ts_code', ''))
		direction = order.get('direction', 'buy')
		order_volume = int(order.get('volume', order.get('quantity', 0)))

		dp = 0.0
		if decision_prices:
			dp = decision_prices.get(symbol, decision_prices.get(order.get('order_id', ''), 0.0))
		if dp == 0.0:
			dp = float(order.get('price', order.get('limit_price', 0)))

		ev = 0
		etv = 0.0
		for t in order_trades:
			v = int(t.get('volume', 0))
			p = float(t.get('price', 0))
			ev += v
			etv += p * v
		aep = etv / ev if ev > 0 else 0.0
		unfilled = max(0, order_volume - ev)

		if dp > 0 and aep > 0:
			sps = (aep - dp) if direction in ('buy', 'BUY') else (dp - aep)
			executed_sf = sps * ev
			opp_cost = sps * unfilled if unfilled > 0 else 0.0
		else:
			sps = 0.0
			executed_sf = 0.0
			opp_cost = 0.0

		commission = sum(float(t.get('commission', 0)) for t in order_trades)
		tax = sum(float(t.get('tax', 0)) for t in order_trades)
		fee = sum(float(t.get('fee', 0)) for t in order_trades)
		explicit = commission + tax + fee

		return {
			'direction': direction, 'order_volume': order_volume,
			'executed_volume': ev, 'unfilled_volume': unfilled,
			'fill_rate': ev / order_volume if order_volume > 0 else 0.0,
			'decision_price': dp, 'avg_exec_price': aep,
			'shortfall_per_share': sps, 'executed_shortfall': executed_sf,
			'opportunity_cost': opp_cost, 'explicit_cost': explicit,
			'total_shortfall_value': executed_sf + opp_cost + explicit,
			'total_volume': ev
		}

	@staticmethod
	def _decompose_shortfall (
			shortfall_results: List[Dict[str, Any]]
		) -> Dict[str, float]:
		"""分解实现缺口"""
		te = to = tx = tv = 0.0
		for sf in shortfall_results:
			te += sf.get('executed_shortfall', 0.0)
			to += sf.get('opportunity_cost', 0.0)
			tx += sf.get('explicit_cost', 0.0)
			tv += sf.get('decision_price', 0.0) * sf.get('order_volume', 0)
		total = te + to + tx
		return {
			'execution_shortfall': te, 'opportunity_cost': to, 'explicit_cost': tx,
			'total_shortfall': total,
			'execution_shortfall_bps': te / tv * 10000 if tv > 0 else 0,
			'opportunity_bps': to / tv * 10000 if tv > 0 else 0,
			'explicit_bps': tx / tv * 10000 if tv > 0 else 0,
			'total_bps': total / tv * 10000 if tv > 0 else 0
		}

	@staticmethod
	def _calculate_shortfall_statistics (
			shortfall_results: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""计算实现缺口统计"""
		if not shortfall_results:
			return {'count': 0}
		vals = np.array([s['total_shortfall_value'] for s in shortfall_results])
		fills = [s.get('fill_rate', 0) for s in shortfall_results]
		return {
			'order_count': len(shortfall_results),
			'total_shortfall': float(np.sum(vals)),
			'mean_shortfall': float(np.mean(vals)), 'median_shortfall': float(np.median(vals)),
			'std_shortfall': float(np.std(vals)),
			'max_shortfall': float(np.max(vals)), 'min_shortfall': float(np.min(vals)),
			'avg_fill_rate': float(np.mean(fills)),
			'positive_shortfall_count': int(np.sum(vals > 0)),
			'negative_shortfall_count': int(np.sum(vals < 0))
		}

	# ---- Cost Optimization helpers ----

	def _analyze_cost_patterns (
			self,
			historical_trades: List[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""分析成本模式"""
		if not historical_trades:
			return {}
		buy_t = [t for t in historical_trades if t.get('direction', '') in ('buy', 'BUY')]
		sell_t = [t for t in historical_trades if t.get('direction', '') in ('sell', 'SELL')]
		buy_costs = [self._estimate_trade_cost(t) for t in buy_t]
		sell_costs = [self._estimate_trade_cost(t) for t in sell_t]

		buckets = {'small': [], 'medium': [], 'large': []}
		for t in historical_trades:
			tv = self._calculate_trade_value(t)
			if tv < 100000:
				buckets['small'].append(t)
			elif tv < 1000000:
				buckets['medium'].append(t)
			else:
				buckets['large'].append(t)

		size_rates = {}
		for bk, trs in buckets.items():
			if trs:
				tc = sum(self._estimate_trade_cost(t) for t in trs)
				tval = sum(self._calculate_trade_value(t) for t in trs)
				size_rates[bk] = tc / tval if tval > 0 else 0
			else:
				size_rates[bk] = 0.0

		all_costs = [self._estimate_trade_cost(t) for t in historical_trades]
		return {
			'buy_avg_cost': float(np.mean(buy_costs)) if buy_costs else 0.0,
			'sell_avg_cost': float(np.mean(sell_costs)) if sell_costs else 0.0,
			'size_cost_rates': size_rates,
			'overall_avg_cost': float(np.mean(all_costs)),
			'cost_volatility': float(np.std(all_costs))
		}

	def _identify_cost_drivers (
			self,
			historical_trades: List[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""识别成本驱动因素"""
		if not historical_trades:
			return {'drivers': []}
		rows = []
		for t in historical_trades:
			tv = self._calculate_trade_value(t)
			cost = self._estimate_trade_cost(t)
			rows.append({'trade_value': tv, 'volume': int(t.get('volume', 0)),
			             'cost': cost, 'cost_rate': cost / tv if tv > 0 else 0})
		df = pd.DataFrame(rows)
		if len(df) < 3:
			return {'drivers': [], 'insufficient_data': True}
		drivers = []
		for col in ['trade_value', 'volume']:
			if col in df.columns and df[col].std() > 0:
				corr = df[col].corr(df['cost_rate'])
				drivers.append({
					'factor': col, 'correlation_with_cost_rate': float(corr),
					'impact': 'positive' if corr > 0 else 'negative',
					'significance': 'high' if abs(corr) > 0.5 else ('medium' if abs(corr) > 0.3 else 'low')
				})
		drivers.sort(key=lambda x: abs(x['correlation_with_cost_rate']), reverse=True)
		return {
			'drivers': drivers,
			'primary_driver': drivers[0]['factor'] if drivers else 'unknown',
			'trade_value_cost_elasticity': float(
				df['trade_value'].corr(df['cost'])) if 'trade_value' in df.columns else 0.0
		}

	@staticmethod
	def _generate_optimization_suggestions (
			cost_patterns: Dict[str, Any],
			cost_drivers: Dict[str, Any],
			cost_parameters: Dict[str, Any],
			optimization_target: str = 'total_cost'
		) -> List[Dict[str, Any]]:
		"""生成成本优化建议"""
		_ = cost_parameters
		suggestions = []
		size_rates = cost_patterns.get('size_cost_rates', {})
		if size_rates:
			sr = size_rates.get('small', 0)
			lr = size_rates.get('large', 0)
			if sr > lr * 1.5:
				suggestions.append({'category': 'trade_sizing',
				                    'suggestion': '考虑合并小额交易以降低单位成本',
				                    'expected_impact': '降低小单成本率约 30-50%', 'priority': 'high'})
			if lr > sr * 1.5:
				suggestions.append({'category': 'trade_sizing',
				                    'suggestion': '考虑拆分大额交易以减少市场冲击',
				                    'expected_impact': '降低冲击成本约 20-40%', 'priority': 'high'})

		primary = cost_drivers.get('primary_driver', '')
		if primary == 'trade_value':
			suggestions.append({'category': 'execution',
			                    'suggestion': '使用算法交易（VWAP/TWAP）优化大单执行',
			                    'expected_impact': '降低执行成本约 15-25%', 'priority': 'high'})
		elif primary == 'volume':
			suggestions.append({'category': 'execution',
			                    'suggestion': '优化下单节奏，避免集中交易',
			                    'expected_impact': '降低滑点成本约 10-20%', 'priority': 'medium'})

		buy_c = cost_patterns.get('buy_avg_cost', 0)
		sell_c = cost_patterns.get('sell_avg_cost', 0)
		if buy_c > sell_c * 1.3:
			suggestions.append({'category': 'direction',
			                    'suggestion': '买方成本显著高于卖方，建议优化买入执行策略',
			                    'expected_impact': '降低买入成本约 10-15%', 'priority': 'medium'})

		if optimization_target == 'slippage':
			suggestions.append({'category': 'execution',
			                    'suggestion': '使用限价单替代市价单，设置合理滑点容忍度',
			                    'expected_impact': '降低滑点成本约 30-50%', 'priority': 'high'})
		elif optimization_target == 'impact':
			suggestions.append({'category': 'execution',
			                    'suggestion': '采用冰山订单或暗池交易隐藏交易意图',
			                    'expected_impact': '降低冲击成本约 20-35%', 'priority': 'high'})

		if not suggestions:
			suggestions.append({'category': 'general',
			                    'suggestion': '当前成本结构合理，持续监控即可',
			                    'expected_impact': '维持现有成本水平', 'priority': 'low'})
		return suggestions

	def _estimate_optimization_potential (
			self,
			historical_trades: List[Dict[str, Any]],
			suggestions: List[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""估计优化潜力"""
		if not historical_trades:
			return {'total_potential_savings': 0.0}
		total_cost = sum(self._estimate_trade_cost(t) for t in historical_trades)
		total_value = sum(self._calculate_trade_value(t) for t in historical_trades)
		rate = 0.0
		for s in suggestions:
			p = s.get('priority', 'low')
			rate += 0.10 if p == 'high' else (0.05 if p == 'medium' else 0.02)
		rate = min(rate, 0.30)
		savings = total_cost * rate
		return {
			'total_potential_savings': savings, 'estimated_savings_rate': rate,
			'current_total_cost': total_cost,
			'current_cost_rate': total_cost / total_value if total_value > 0 else 0,
			'optimized_cost_rate': (total_cost - savings) / total_value if total_value > 0 else 0,
			'suggestion_count': len(suggestions),
			'high_priority_count': sum(1 for s in suggestions if s.get('priority') == 'high')
		}