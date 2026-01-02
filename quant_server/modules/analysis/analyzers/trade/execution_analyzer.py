#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
执行分析器

负责分析订单执行质量，包括执行时间、成交率、价格改进等。
"""

from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Any, Union
from datetime import datetime, date, timedelta
import numpy as np
import pandas as pd
from scipy import stats

from core.utils.math_utils.statistic_calculator import StatisticCalculator


class ExecutionAnalyzer:
	"""执行分析器"""

	def __init__ (self):
		"""初始化执行分析器"""
		self.stat_calc = StatisticCalculator()

	def analyze_execution_quality (
			self,
			orders: List[Dict[str, Any]],
			trades: List[Dict[str, Any]],
			market_data: Optional[Dict[str, Any]] = None
	) -> Dict[str, Any]:
		"""
		分析执行质量

		Args:
			orders: 订单记录列表
			trades: 交易记录列表
			market_data: 市场数据（可选）

		Returns:
			执行质量分析结果
		"""
		try:
			if not orders:
				return self._empty_execution_analysis()

			# 匹配订单和交易
			order_executions = self._match_orders_with_executions(orders, trades)

			if not order_executions:
				return {'error': '无法匹配订单和交易'}

			# 分析执行时间
			execution_time_analysis = self._analyze_execution_time(order_executions)

			# 分析成交率
			fill_rate_analysis = self._analyze_fill_rate(orders, order_executions)

			# 分析价格改进
			price_improvement_analysis = self._analyze_price_improvement(order_executions)

			# 分析执行效率
			execution_efficiency = self._analyze_execution_efficiency(order_executions, market_data)

			# 分析执行一致性
			execution_consistency = self._analyze_execution_consistency(order_executions)

			# 构建结果
			result = {
				'execution_time': execution_time_analysis,
				'fill_rate': fill_rate_analysis,
				'price_improvement': price_improvement_analysis,
				'execution_efficiency': execution_efficiency,
				'execution_consistency': execution_consistency,
				'order_executions': order_executions,
				'summary': self._create_execution_summary(
					execution_time_analysis,
					fill_rate_analysis,
					price_improvement_analysis,
					execution_efficiency
				)
			}

			return result

		except Exception as e:
			raise ValueError(f"执行质量分析失败: {str(e)}")

	def analyze_vwap_performance (
			self,
			orders: List[Dict[str, Any]],
			trades: List[Dict[str, Any]],
			market_vwap: Dict[str, pd.Series]
	) -> Dict[str, Any]:
		"""
		分析VWAP执行表现

		Args:
			orders: 订单记录列表
			trades: 交易记录列表
			market_vwap: 市场VWAP数据 {证券代码: VWAP序列}

		Returns:
			VWAP执行表现分析结果
		"""
		try:
			# 匹配订单和交易
			order_executions = self._match_orders_with_executions(orders, trades)

			if not order_executions:
				return {'error': '无法匹配订单和交易'}

			vwap_results = []
			total_vwap_beat = 0.0
			total_volume = 0.0

			for order_id, execution in order_executions.items():
				order = execution['order']
				execution_trades = execution['trades']

				if not execution_trades:
					continue

				# 获取证券代码
				ts_code = order.get('ts_code')
				if not ts_code or ts_code not in market_vwap:
					continue

				# 计算订单的VWAP
				order_vwap = self._calculate_order_vwap(execution_trades)

				# 获取市场VWAP
				market_vwap_series = market_vwap[ts_code]

				# 计算订单执行时间的市场VWAP
				order_market_vwap = self._calculate_order_market_vwap(
					execution_trades, market_vwap_series
				)

				# 计算VWAP表现
				vwap_performance = order_vwap - order_market_vwap
				vwap_beat_pct = (order_market_vwap - order_vwap) / order_market_vwap if order_market_vwap != 0 else 0

				# 计算执行量
				order_volume = sum(t.get('volume', 0) for t in execution_trades)

				vwap_results.append({
					'order_id': order_id,
					'order_vwap': order_vwap,
					'market_vwap': order_market_vwap,
					'vwap_performance': vwap_performance,
					'vwap_beat_pct': vwap_beat_pct,
					'order_volume': order_volume,
					'direction': order.get('direction', 'unknown')
				})

				total_vwap_beat += vwap_performance * order_volume
				total_volume += order_volume

			# 计算加权平均VWAP表现
			weighted_vwap_performance = total_vwap_beat / total_volume if total_volume > 0 else 0

			# VWAP表现统计
			vwap_statistics = self._calculate_vwap_statistics(vwap_results)

			# VWAP表现归因
			vwap_attribution = self._attribute_vwap_performance(vwap_results)

			return {
				'order_vwap_results': vwap_results,
				'weighted_vwap_performance': weighted_vwap_performance,
				'vwap_statistics': vwap_statistics,
				'vwap_attribution': vwap_attribution,
				'summary': {
					'total_orders_analyzed': len(vwap_results),
					'total_volume': total_volume,
					'vwap_beat_rate': len([r for r in vwap_results if r['vwap_performance'] > 0]) / len(
						vwap_results) if vwap_results else 0,
					'avg_vwap_beat_pct': np.mean([r['vwap_beat_pct'] for r in vwap_results]) if vwap_results else 0
				}
			}

		except Exception as e:
			raise ValueError(f"VWAP执行表现分析失败: {str(e)}")

	def analyze_market_impact (
			self,
			trades: List[Dict[str, Any]],
			market_data: Dict[str, pd.DataFrame],
			estimation_method: str = 'pre_post'
	) -> Dict[str, Any]:
		"""
		分析市场冲击

		Args:
			trades: 交易记录列表
			market_data: 市场数据 {证券代码: DataFrame}
			estimation_method: 估计方法 ('pre_post', 'volume', 'propensity')

		Returns:
			市场冲击分析结果
		"""
		try:
			if not trades:
				return {'error': '交易数据为空'}

			impact_results = []

			for trade in trades:
				ts_code = trade.get('ts_code')
				if not ts_code or ts_code not in market_data:
					continue

				# 获取交易详情
				trade_time = trade.get('trade_time')
				trade_price = trade.get('price', 0)
				trade_volume = trade.get('volume', 0)
				direction = trade.get('direction', 'buy')

				if not trade_time or trade_price == 0 or trade_volume == 0:
					continue

				# 获取市场数据
				stock_data = market_data[ts_code]

				# 估计市场冲击
				market_impact = self._estimate_trade_impact(
					trade_time, trade_price, trade_volume, direction,
					stock_data, estimation_method
				)

				if market_impact is not None:
					impact_results.append({
						'trade_id': trade.get('trade_id', f'trade_{len(impact_results)}'),
						'ts_code': ts_code,
						'trade_time': trade_time,
						'trade_price': trade_price,
						'trade_volume': trade_volume,
						'direction': direction,
						'market_impact': market_impact,
						'impact_per_share': market_impact / trade_volume if trade_volume > 0 else 0,
						'impact_pct': market_impact / (
									trade_price * trade_volume) if trade_price * trade_volume > 0 else 0
					})

			# 市场冲击统计
			impact_statistics = self._calculate_impact_statistics(impact_results)

			# 市场冲击模型
			impact_model = self._estimate_impact_model(impact_results)

			return {
				'trade_impacts': impact_results,
				'impact_statistics': impact_statistics,
				'impact_model': impact_model,
				'estimation_method': estimation_method,
				'summary': {
					'total_trades_analyzed': len(impact_results),
					'avg_market_impact': np.mean([r['market_impact'] for r in impact_results]) if impact_results else 0,
					'avg_impact_pct': np.mean([r['impact_pct'] for r in impact_results]) if impact_results else 0,
					'buy_impact': np.mean(
						[r['market_impact'] for r in impact_results if r['direction'] == 'buy']) if any(
						r['direction'] == 'buy' for r in impact_results) else 0,
					'sell_impact': np.mean(
						[r['market_impact'] for r in impact_results if r['direction'] == 'sell']) if any(
						r['direction'] == 'sell' for r in impact_results) else 0
				}
			}

		except Exception as e:
			raise ValueError(f"市场冲击分析失败: {str(e)}")

	def analyze_liquidity_provision (
			self,
			trades: List[Dict[str, Any]],
			order_book_data: Optional[Dict[str, Any]] = None,
			market_regime: str = 'normal'
	) -> Dict[str, Any]:
		"""
		分析流动性提供表现

		Args:
			trades: 交易记录列表
			order_book_data: 订单簿数据（可选）
			market_regime: 市场状态 ('normal', 'volatile', 'crisis')

		Returns:
			流动性提供分析结果
		"""
		try:
			if not trades:
				return {'error': '交易数据为空'}

			liquidity_results = []

			for trade in trades:
				# 分析每笔交易的流动性提供特征
				liquidity_metrics = self._analyze_trade_liquidity(trade, order_book_data, market_regime)

				if liquidity_metrics:
					liquidity_results.append({
						'trade_id': trade.get('trade_id', f'trade_{len(liquidity_results)}'),
						**liquidity_metrics
					})

			# 流动性统计
			liquidity_statistics = self._calculate_liquidity_statistics(liquidity_results)

			# 流动性提供效率
			liquidity_efficiency = self._analyze_liquidity_efficiency(liquidity_results)

			# 流动性提供建议
			liquidity_suggestions = self._generate_liquidity_suggestions(liquidity_results, market_regime)

			return {
				'trade_liquidity': liquidity_results,
				'liquidity_statistics': liquidity_statistics,
				'liquidity_efficiency': liquidity_efficiency,
				'liquidity_suggestions': liquidity_suggestions,
				'market_regime': market_regime,
				'summary': {
					'total_trades_analyzed': len(liquidity_results),
					'liquidity_provider_score': self._calculate_liquidity_score(liquidity_results),
					'avg_spread_capture': np.mean(
						[r.get('spread_capture', 0) for r in liquidity_results]) if liquidity_results else 0,
					'avg_depth_utilization': np.mean(
						[r.get('depth_utilization', 0) for r in liquidity_results]) if liquidity_results else 0
				}
			}

		except Exception as e:
			raise ValueError(f"流动性提供分析失败: {str(e)}")

	def _empty_execution_analysis (self) -> Dict[str, Any]:
		"""返回空的执行分析结果"""
		return {
			'execution_time': {},
			'fill_rate': {},
			'price_improvement': {},
			'execution_efficiency': {},
			'execution_consistency': {},
			'summary': {}
		}

	def _match_orders_with_executions (
			self,
			orders: List[Dict[str, Any]],
			trades: List[Dict[str, Any]]
	) -> Dict[str, Dict[str, Any]]:
		"""匹配订单和成交"""
		order_executions = {}

		# 按订单ID组织交易
		for order in orders:
			order_id = order.get('order_id')
			if not order_id:
				continue

			# 查找该订单的所有成交
			order_trades = [t for t in trades if t.get('order_id') == order_id]

			order_executions[order_id] = {
				'order': order,
				'trades': order_trades,
				'total_volume': sum(t.get('volume', 0) for t in order_trades),
				'total_value': sum(t.get('price', 0) * t.get('volume', 0) for t in order_trades)
			}

		return order_executions

	def _analyze_execution_time (
			self,
			order_executions: Dict[str, Dict[str, Any]]
	) -> Dict[str, Any]:
		"""分析执行时间"""
		execution_times = []
		partial_execution_times = []

		for order_id, execution in order_executions.items():
			order = execution['order']
			trades = execution['trades']

			if not trades:
				continue

			# 获取订单提交时间
			submitted_at = order.get('submitted_at')
			if not submitted_at:
				continue

			# 计算每笔成交的执行时间
			for trade in trades:
				trade_time = trade.get('trade_time')
				if not trade_time:
					continue

				# 计算执行时间（秒）
				if isinstance(submitted_at, str):
					submitted_dt = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
				else:
					submitted_dt = submitted_at

				if isinstance(trade_time, str):
					trade_dt = datetime.fromisoformat(trade_time.replace('Z', '+00:00'))
				else:
					trade_dt = trade_time

				exec_time = (trade_dt - submitted_dt).total_seconds()
				execution_times.append(exec_time)

			# 如果订单有多个成交，计算部分成交时间
			if len(trades) > 1:
				first_trade = min(trades, key=lambda t: t.get('trade_time', datetime.min))
				last_trade = max(trades, key=lambda t: t.get('trade_time', datetime.min))

				if isinstance(first_trade.get('trade_time'), str):
					first_dt = datetime.fromisoformat(first_trade['trade_time'].replace('Z', '+00:00'))
				else:
					first_dt = first_trade.get('trade_time')

				if isinstance(last_trade.get('trade_time'), str):
					last_dt = datetime.fromisoformat(last_trade['trade_time'].replace('Z', '+00:00'))
				else:
					last_dt = last_trade.get('trade_time')

				partial_time = (last_dt - first_dt).total_seconds()
				partial_execution_times.append(partial_time)

		# 计算统计量
		if not execution_times:
			return {'no_data': True}

		return {
			'execution_times': execution_times,
			'partial_execution_times': partial_execution_times,
			'statistics': {
				'mean': float(np.mean(execution_times)),
				'median': float(np.median(execution_times)),
				'std': float(np.std(execution_times)),
				'min': float(np.min(execution_times)),
				'max': float(np.max(execution_times)),
				'q1': float(np.percentile(execution_times, 25)),
				'q3': float(np.percentile(execution_times, 75))
			},
			'distribution': self._analyze_time_distribution(execution_times)
		}

	def _analyze_fill_rate (
			self,
			orders: List[Dict[str, Any]],
			order_executions: Dict[str, Dict[str, Any]]
	) -> Dict[str, Any]:
		"""分析成交率"""
		fill_rates = []
		order_fill_details = []

		for order in orders:
			order_id = order.get('order_id')
			if not order_id:
				continue

			# 获取订单信息
			order_volume = order.get('volume', 0)
			order_status = order.get('status', 'unknown')

			# 获取成交信息
			execution = order_executions.get(order_id, {})
			executed_volume = execution.get('total_volume', 0)

			# 计算成交率
			if order_volume > 0:
				fill_rate = executed_volume / order_volume
			else:
				fill_rate = 0.0

			fill_rates.append(fill_rate)

			order_fill_details.append({
				'order_id': order_id,
				'order_volume': order_volume,
				'executed_volume': executed_volume,
				'fill_rate': fill_rate,
				'order_status': order_status
			})

		# 按订单状态分析
		status_fill_rates = {}
		for status in ['filled', 'partial_filled', 'cancelled', 'rejected']:
			status_orders = [d for d in order_fill_details if d['order_status'] == status]
			if status_orders:
				status_fill_rates[status] = np.mean([d['fill_rate'] for d in status_orders])

		return {
			'fill_rates': fill_rates,
			'order_fill_details': order_fill_details,
			'statistics': {
				'mean_fill_rate': float(np.mean(fill_rates)) if fill_rates else 0,
				'median_fill_rate': float(np.median(fill_rates)) if fill_rates else 0,
				'std_fill_rate': float(np.std(fill_rates)) if fill_rates else 0,
				'perfect_fill_rate': len([fr for fr in fill_rates if fr == 1.0]) / len(fill_rates) if fill_rates else 0
			},
			'status_fill_rates': status_fill_rates
		}

	def _analyze_price_improvement (
			self,
			order_executions: Dict[str, Dict[str, Any]]
	) -> Dict[str, Any]:
		"""分析价格改进"""
		price_improvements = []
		order_improvements = []

		for order_id, execution in order_executions.items():
			order = execution['order']
			trades = execution['trades']

			if not trades:
				continue

			# 获取订单信息
			order_price = order.get('price', 0)
			order_type = order.get('order_type', 'limit')
			direction = order.get('direction', 'buy')

			if order_type != 'limit' or order_price == 0:
				continue

			# 计算每笔成交的价格改进
			for trade in trades:
				trade_price = trade.get('price', 0)
				if trade_price == 0:
					continue

				# 价格改进计算
				if direction == 'buy':
					# 买入：成交价低于限价为改进
					improvement = order_price - trade_price
				else:
					# 卖出：成交价高于限价为改进
					improvement = trade_price - order_price

				improvement_pct = improvement / order_price if order_price > 0 else 0

				price_improvements.append(improvement)
				order_improvements.append({
					'order_id': order_id,
					'direction': direction,
					'order_price': order_price,
					'trade_price': trade_price,
					'improvement': improvement,
					'improvement_pct': improvement_pct
				})

		# 计算统计量
		if not price_improvements:
			return {'no_data': True}

		return {
			'price_improvements': price_improvements,
			'order_improvements': order_improvements,
			'statistics': {
				'mean_improvement': float(np.mean(price_improvements)),
				'median_improvement': float(np.median(price_improvements)),
				'std_improvement': float(np.std(price_improvements)),
				'positive_improvement_rate': len([i for i in price_improvements if i > 0]) / len(
					price_improvements) if price_improvements else 0,
				'buy_improvement': np.mean(
					[i['improvement'] for i in order_improvements if i['direction'] == 'buy']) if any(
					i['direction'] == 'buy' for i in order_improvements) else 0,
				'sell_improvement': np.mean(
					[i['improvement'] for i in order_improvements if i['direction'] == 'sell']) if any(
					i['direction'] == 'sell' for i in order_improvements) else 0
			}
		}

	def _analyze_execution_efficiency (
			self,
			order_executions: Dict[str, Dict[str, Any]],
			market_data: Optional[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""分析执行效率"""
		efficiency_metrics = []

		for order_id, execution in order_executions.items():
			order = execution['order']
			trades = execution['trades']

			if not trades:
				continue

			# 计算执行效率指标
			metrics = {
				'order_id': order_id,
				'volume_efficiency': self._calculate_volume_efficiency(order, trades),
				'timing_efficiency': self._calculate_timing_efficiency(order, trades),
				'price_efficiency': self._calculate_price_efficiency(order, trades, market_data),
				'urgency_efficiency': self._calculate_urgency_efficiency(order, trades)
			}

			efficiency_metrics.append(metrics)

		# 计算综合效率
		if not efficiency_metrics:
			return {'no_data': True}

		# 提取各项效率指标
		volume_eff = [m['volume_efficiency'] for m in efficiency_metrics]
		timing_eff = [m['timing_efficiency'] for m in efficiency_metrics]
		price_eff = [m['price_efficiency'] for m in efficiency_metrics]
		urgency_eff = [m['urgency_efficiency'] for m in efficiency_metrics]

		# 计算综合效率得分
		composite_scores = []
		for i in range(len(efficiency_metrics)):
			score = 0.25 * volume_eff[i] + 0.25 * timing_eff[i] + 0.35 * price_eff[i] + 0.15 * urgency_eff[i]
			composite_scores.append(score)
			efficiency_metrics[i]['composite_efficiency'] = score

		return {
			'efficiency_metrics': efficiency_metrics,
			'composite_scores': composite_scores,
			'statistics': {
				'mean_composite': float(np.mean(composite_scores)) if composite_scores else 0,
				'median_composite': float(np.median(composite_scores)) if composite_scores else 0,
				'volume_efficiency': float(np.mean(volume_eff)) if volume_eff else 0,
				'timing_efficiency': float(np.mean(timing_eff)) if timing_eff else 0,
				'price_efficiency': float(np.mean(price_eff)) if price_eff else 0,
				'urgency_efficiency': float(np.mean(urgency_eff)) if urgency_eff else 0
			}
		}

	def _analyze_execution_consistency (
			self,
			order_executions: Dict[str, Dict[str, Any]]
	) -> Dict[str, Any]:
		"""分析执行一致性"""
		# 按证券代码分组
		security_executions = {}

		for order_id, execution in order_executions.items():
			order = execution['order']
			trades = execution['trades']

			if not trades:
				continue

			ts_code = order.get('ts_code')
			if not ts_code:
				continue

			if ts_code not in security_executions:
				security_executions[ts_code] = []

			# 计算该订单的执行指标
			order_metrics = {
				'order_id': order_id,
				'fill_rate': execution['total_volume'] / order.get('volume', 1) if order.get('volume', 0) > 0 else 0,
				'avg_execution_time': self._calculate_avg_execution_time(order, trades),
				'price_improvement': self._calculate_avg_price_improvement(order, trades)
			}

			security_executions[ts_code].append(order_metrics)

		# 分析一致性
		consistency_results = {}

		for ts_code, executions in security_executions.items():
			if len(executions) < 3:  # 至少需要3个订单才能分析一致性
				continue

			# 提取指标序列
			fill_rates = [e['fill_rate'] for e in executions]
			exec_times = [e['avg_execution_time'] for e in executions if e['avg_execution_time'] is not None]
			price_improv = [e['price_improvement'] for e in executions if e['price_improvement'] is not None]

			# 计算变异系数（标准差/均值）
			consistency_metrics = {}

			if fill_rates and np.mean(fill_rates) > 0:
				consistency_metrics['fill_rate_cv'] = np.std(fill_rates) / np.mean(fill_rates)

			if exec_times and np.mean(exec_times) > 0:
				consistency_metrics['exec_time_cv'] = np.std(exec_times) / np.mean(exec_times)

			if price_improv and np.mean(np.abs(price_improv)) > 0:
				consistency_metrics['price_improv_cv'] = np.std(price_improv) / np.mean(np.abs(price_improv))

			# 计算综合一致性得分
			if consistency_metrics:
				# 一致性得分 = 1 - 平均变异系数（归一化）
				avg_cv = np.mean(list(consistency_metrics.values()))
				consistency_score = max(0, 1 - avg_cv)
				consistency_metrics['consistency_score'] = consistency_score

			consistency_results[ts_code] = consistency_metrics

		return {
			'security_consistency': consistency_results,
			'overall_consistency': self._calculate_overall_consistency(consistency_results)
		}

	def _create_execution_summary (
			self,
			execution_time: Dict[str, Any],
			fill_rate: Dict[str, Any],
			price_improvement: Dict[str, Any],
			execution_efficiency: Dict[str, Any]
	) -> Dict[str, Any]:
		"""创建执行摘要"""
		return {
			'avg_execution_time': execution_time.get('statistics', {}).get('mean', 0),
			'median_execution_time': execution_time.get('statistics', {}).get('median', 0),
			'avg_fill_rate': fill_rate.get('statistics', {}).get('mean_fill_rate', 0),
			'perfect_fill_rate': fill_rate.get('statistics', {}).get('perfect_fill_rate', 0),
			'avg_price_improvement': price_improvement.get('statistics', {}).get('mean_improvement', 0),
			'positive_improvement_rate': price_improvement.get('statistics', {}).get('positive_improvement_rate', 0),
			'composite_efficiency': execution_efficiency.get('statistics', {}).get('mean_composite', 0),
			'execution_quality_rating': self._calculate_quality_rating(
				execution_time, fill_rate, price_improvement, execution_efficiency
			)
		}