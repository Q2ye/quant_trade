#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
执行分析器

负责分析订单执行质量，包括执行时间、成交率、价格改进等。
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
from scipy import stats


class ExecutionAnalyzer:
	"""执行分析器"""

	def __init__ (self):
		"""初始化执行分析器"""
		pass

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

	@staticmethod
	def _empty_execution_analysis () -> Dict[str, Any]:
		"""返回空执行分析结果"""
		return {
			'execution_time': {},
			'fill_rate': {},
			'price_improvement': {},
			'execution_efficiency': {},
			'execution_consistency': {},
			'summary': {}
		}

	@staticmethod
	def _match_orders_with_executions (
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

	@staticmethod
	def _analyze_fill_rate (
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

	@staticmethod
	def _analyze_price_improvement (
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
				consistency_score = max(0.0, 1.0 - float(avg_cv))
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

	@staticmethod
	def _calculate_order_vwap (
			execution_trades: List[Dict[str, Any]]
		) -> float:
		"""计算订单执行VWAP"""
		total_value = 0.0
		total_volume = 0.0
		for t in execution_trades:
			price = float(t.get("price", 0))
			volume = int(t.get("volume", 0))
			total_value += price * volume
			total_volume += volume
		return total_value / total_volume if total_volume > 0 else 0.0

	@staticmethod
	def _calculate_order_market_vwap (
			execution_trades: List[Dict[str, Any]],
			market_vwap_series: pd.Series
		) -> float:
		"""计算订单执行期间的市场VWAP"""
		vwap_values: List[float] = []
		volumes: List[int] = []
		for t in execution_trades:
			trade_time = t.get("trade_time")
			if trade_time is None:
				continue
			try:
				ts = pd.Timestamp(trade_time)
				market_index = market_vwap_series.index
				if ts in market_index:
					vwap_values.append(float(market_vwap_series.loc[ts]))
					volumes.append(int(t.get("volume", 0)))
				else:
					indices: pd.Index = market_index
					search_index = pd.Index([ts])
					idx = int(indices.get_indexer(search_index, method="nearest")[0])
					if idx >= 0:
						vwap_values.append(float(market_vwap_series.values[idx]))
						volumes.append(int(t.get("volume", 0)))
			except (KeyError, IndexError, TypeError):
				continue
		if not vwap_values or sum(volumes) == 0:
			return 0.0
		weighted = sum(v * w for v, w in zip(vwap_values, volumes))
		return weighted / sum(volumes)

	@staticmethod
	def _calculate_vwap_statistics (
			vwap_results: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""计算VWAP执行统计"""
		if not vwap_results:
			return {"count": 0}
		performances = np.array([r["vwap_performance"] for r in vwap_results])
		beat_pcts = np.array([r["vwap_beat_pct"] for r in vwap_results])
		volumes = np.array([r.get("order_volume", 0) for r in vwap_results])
		return {
			"count": len(vwap_results),
			"mean_performance": float(np.mean(performances)),
			"median_performance": float(np.median(performances)),
			"std_performance": float(np.std(performances)),
			"mean_beat_pct": float(np.mean(beat_pcts)),
			"beat_rate": float(np.sum(performances > 0) / len(performances)),
			"total_volume": int(np.sum(volumes)),
			"vwap_winners": int(np.sum(performances > 0)),
			"vwap_losers": int(np.sum(performances < 0)),
		}

	@staticmethod
	def _attribute_vwap_performance (
			vwap_results: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""VWAP表现归因分析"""
		if not vwap_results:
			return {"attribution": {}}
		buys = [r for r in vwap_results if r.get("direction") == "buy"]
		sells = [r for r in vwap_results if r.get("direction") == "sell"]
		buy_perf = np.mean([r["vwap_performance"] for r in buys]) if buys else 0.0
		sell_perf = np.mean([r["vwap_performance"] for r in sells]) if sells else 0.0
		small_orders = [r for r in vwap_results if r.get("order_volume", 0) < 10000]
		large_orders = [r for r in vwap_results if r.get("order_volume", 0) >= 10000]
		small_perf = np.mean([r["vwap_performance"] for r in small_orders]) if small_orders else 0.0
		large_perf = np.mean([r["vwap_performance"] for r in large_orders]) if large_orders else 0.0
		return {
			"attribution": {
				"direction": {
					"buy_vwap_performance": float(buy_perf),
					"sell_vwap_performance": float(sell_perf),
					"preferred_direction": "buy" if buy_perf < sell_perf else "sell"
				},
				"size": {
					"small_order_performance": float(small_perf),
					"large_order_performance": float(large_perf),
					"preferred_size": "small" if small_perf < large_perf else "large"
				}
			}
		}

	def _estimate_trade_impact (
			self,
			trade_time: Any,
			trade_price: float,
			trade_volume: int,
			direction: str,
			stock_data: pd.DataFrame,
			estimation_method: str
		) -> Optional[float]:
		"""估计单笔交易的市场冲击"""
		try:
			if estimation_method == "pre_post":
				return self._estimate_pre_post_impact(
					trade_time, trade_price, trade_volume, direction, stock_data
				)
			elif estimation_method == "volume":
				return self._estimate_volume_based_impact(trade_price, trade_volume)
			elif estimation_method == "propensity":
				return self._estimate_propensity_impact(trade_price, trade_volume, stock_data)
			else:
				return self._estimate_pre_post_impact(
					trade_time, trade_price, trade_volume, direction, stock_data
				)
		except (KeyError, IndexError, TypeError, ValueError):
			return None

	@staticmethod
	def _estimate_pre_post_impact (
			trade_time: Any,
			trade_price: float,
			trade_volume: int,
			direction: str,
			stock_data: pd.DataFrame
		) -> Optional[float]:
		"""交易前后价格对比法估计冲击"""
		_ = trade_price
		try:
			ts = pd.Timestamp(trade_time)
			if "close" not in stock_data.columns:
				return None
			before = stock_data[stock_data.index <= ts]
			after = stock_data[stock_data.index >= ts]
			if before.empty or after.empty:
				return None
			price_before = float(before["close"].iloc[-1])
			price_after = float(after["close"].iloc[0])
			if price_before == 0:
				return None
			price_change = price_after - price_before
			if direction in ("sell", "SELL"):
				price_change = -price_change
			return price_change * trade_volume
		except (KeyError, IndexError, TypeError):
			return None

	@staticmethod
	def _estimate_volume_based_impact (
			trade_price: float,
			trade_volume: int
		) -> float:
		"""基于成交量的冲击估计（平方根模型）"""
		participation_rate = 0.01
		impact_bps = 10 * (participation_rate ** 0.5)
		return trade_price * trade_volume * impact_bps / 10000

	@staticmethod
	def _estimate_propensity_impact (
			trade_price: float,
			trade_volume: int,
			stock_data: pd.DataFrame
		) -> float:
		"""倾向性得分冲击估计"""
		avg_volume = float(stock_data.get("volume", pd.Series([trade_volume])).mean())
		if avg_volume > 0:
			volume_ratio = trade_volume / avg_volume
			impact_bps = 5 * (volume_ratio ** 0.6) * 100
		else:
			impact_bps = 10.0
		return trade_price * trade_volume * impact_bps / 10000

	@staticmethod
	def _calculate_impact_statistics (
			impact_results: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""计算市场冲击统计"""
		if not impact_results:
			return {"count": 0}
		impacts = np.array([r["market_impact"] for r in impact_results])
		impact_pcts = np.array([r.get("impact_pct", 0) for r in impact_results])
		return {
			"count": len(impact_results),
			"total_impact": float(np.sum(impacts)),
			"mean_impact": float(np.mean(impacts)),
			"median_impact": float(np.median(impacts)),
			"std_impact": float(np.std(impacts)),
			"mean_impact_pct": float(np.mean(impact_pcts)),
			"p95_impact": float(np.percentile(impacts, 95)),
			"p99_impact": float(np.percentile(impacts, 99)),
			"positive_impact_rate": float(np.sum(impacts > 0) / len(impacts)),
		}

	@staticmethod
	def _estimate_impact_model (
			impact_results: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""估计冲击模型参数（幂律模型: I = k * V^alpha）"""
		if len(impact_results) < 5:
			return {"model": "insufficient_data"}
		volumes = np.array([r["trade_volume"] for r in impact_results])
		impacts = np.array([r["market_impact"] for r in impact_results])
		log_v = np.log(volumes[volumes > 0])
		log_i = np.log(np.abs(impacts[volumes > 0]) + 1e-10)
		if len(log_v) < 5:
			return {"model": "insufficient_data"}
		slope, intercept, r_value, p_value, std_err = stats.linregress(log_v, log_i)
		k = np.exp(intercept)
		predictions = k * (volumes ** slope)
		residuals = impacts - predictions
		return {
			"model": "power_law",
			"formula": f"I = {k:.6f} * V^{slope:.3f}",
			"alpha": float(slope),
			"k": float(k),
			"r_squared": float(r_value ** 2),
			"p_value": float(p_value),
			"rmse": float(np.sqrt(np.mean(residuals ** 2))),
			"sample_size": len(impact_results)
		}

	@staticmethod
	def _analyze_trade_liquidity (
			trade: Dict[str, Any],
			order_book_data: Optional[Dict[str, Any]],
			market_regime: str
		) -> Optional[Dict[str, Any]]:
		"""分析单笔交易的流动性特征"""
		_ = order_book_data
		volume = int(trade.get("volume", 0))
		price = float(trade.get("price", 0))
		direction = trade.get("direction", "buy")
		trade_value = price * volume
		regime_spreads = {"normal": 0.001, "volatile": 0.003, "crisis": 0.01}
		estimated_spread = regime_spreads.get(market_regime, 0.001)
		spread_capture = estimated_spread * (0.5 if direction == "buy" else 0.5)
		market_depth = estimated_spread * price * 100000
		depth_utilization = trade_value / market_depth if market_depth > 0 else 0
		liquidity_consumption_time = int(volume / 1000 * 60) if market_regime == "normal" else int(volume / 500 * 60)
		return {
			"estimated_spread": estimated_spread,
			"spread_capture": spread_capture,
			"depth_utilization": min(depth_utilization, 1.0),
			"liquidity_consumption_time": liquidity_consumption_time,
			"market_regime": market_regime,
			"trade_value": trade_value
		}

	@staticmethod
	def _calculate_liquidity_statistics (
			liquidity_results: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""计算流动性统计"""
		if not liquidity_results:
			return {"count": 0}
		spread_captures = np.array([r.get("spread_capture", 0) for r in liquidity_results])
		depth_utils = np.array([r.get("depth_utilization", 0) for r in liquidity_results])
		consume_times = np.array([r.get("liquidity_consumption_time", 0) for r in liquidity_results])
		return {
			"count": len(liquidity_results),
			"mean_spread_capture": float(np.mean(spread_captures)),
			"std_spread_capture": float(np.std(spread_captures)),
			"mean_depth_utilization": float(np.mean(depth_utils)),
			"max_depth_utilization": float(np.max(depth_utils)),
			"mean_consumption_time_seconds": float(np.mean(consume_times)),
			"high_depth_utilization_rate": float(np.sum(depth_utils > 0.5) / len(depth_utils)),
		}

	@staticmethod
	def _analyze_liquidity_efficiency (
			liquidity_results: List[Dict[str, Any]]
		) -> Dict[str, Any]:
		"""分析流动性提供效率"""
		if not liquidity_results:
			return {"efficiency_score": 0.0}
		depth_utils = np.array([r.get("depth_utilization", 0) for r in liquidity_results])
		spread_caps = np.array([r.get("spread_capture", 0) for r in liquidity_results])
		depth_score = 1.0 - np.clip(np.mean(depth_utils), 0, 1)
		spread_score = np.clip(np.mean(spread_caps) / 0.002, 0, 1) if np.mean(spread_caps) > 0 else 0.5
		efficiency = 0.4 * float(depth_score) + 0.4 * float(spread_score) + 0.2 * min(len(liquidity_results) / 100, 1.0)
		return {
			"efficiency_score": float(efficiency),
			"depth_score": float(depth_score),
			"spread_score": float(spread_score),
			"rating": "high" if efficiency > 0.7 else ("medium" if efficiency > 0.4 else "low")
		}

	@staticmethod
	def _generate_liquidity_suggestions (
			liquidity_results: List[Dict[str, Any]],
			market_regime: str
		) -> List[Dict[str, Any]]:
		"""生成流动性优化建议"""
		suggestions = []
		if not liquidity_results:
			suggestions.append({
				"category": "general",
				"suggestion": "暂无足够数据，建议积累更多交易记录后再分析",
				"priority": "low"
			})
			return suggestions
		depth_utils = np.array([r.get("depth_utilization", 0) for r in liquidity_results])
		avg_depth = float(np.mean(depth_utils))
		if avg_depth > 0.5:
			suggestions.append({
				"category": "depth",
				"suggestion": "深度利用率过高，建议拆分大单或使用算法交易",
				"expected_impact": "降低冲击成本 20-30%",
				"priority": "high"
			})
		if market_regime == "volatile":
			suggestions.append({
				"category": "timing",
				"suggestion": "高波动环境下建议降低单笔交易规模，增加交易间隔",
				"expected_impact": "降低波动相关损失 15-25%",
				"priority": "medium"
			})
		elif market_regime == "crisis":
			suggestions.append({
				"category": "timing",
				"suggestion": "危机模式下建议暂停大额交易，仅维持必要流动性",
				"expected_impact": "避免极端行情损失",
				"priority": "high"
			})
		if not suggestions:
			suggestions.append({
				"category": "general",
				"suggestion": "当前流动性管理良好，建议维持现有策略",
				"priority": "low"
			})
		return suggestions

	@staticmethod
	def _calculate_liquidity_score (
			liquidity_results: List[Dict[str, Any]]
		) -> float:
		"""计算流动性提供者综合得分"""
		if not liquidity_results:
			return 0.0
		depth_utils = np.array([r.get("depth_utilization", 0) for r in liquidity_results])
		spread_caps = np.array([r.get("spread_capture", 0) for r in liquidity_results])
		depth_score = max(0.0, 1.0 - float(np.mean(depth_utils)))
		spread_score = min(1.0, float(np.mean(spread_caps)) / 0.003)
		volume_score = min(1.0, int(len(liquidity_results)) / 50)
		return float(0.35 * depth_score + 0.45 * spread_score + 0.20 * volume_score)

	@staticmethod
	def _analyze_time_distribution (
			execution_times: List[float]
		) -> Dict[str, Any]:
		"""分析执行时间分布"""
		if not execution_times:
			return {"buckets": {}}
		times = np.array(execution_times)
		buckets_def = [
			("instant", 0, 1),
			("very_fast", 1, 10),
			("fast", 10, 60),
			("moderate", 60, 300),
			("slow", 300, 1800),
			("very_slow", 1800, float("inf")),
		]
		buckets = {}
		for name, lo, hi in buckets_def:
			count = int(np.sum((times >= lo) & (times < hi)))
			buckets[name] = {"range": f"{lo}-{hi}s", "count": count, "pct": float(count) / len(times)}
		return {"buckets": buckets, "total": len(times)}

	@staticmethod
	def _calculate_volume_efficiency (
			order: Dict[str, Any],
			trades: List[Dict[str, Any]]
		) -> float:
		"""计算成交量效率"""
		order_volume = int(order.get("volume", order.get("quantity", 0)))
		executed_volume = sum(int(t.get("volume", 0)) for t in trades)
		if order_volume <= 0:
			return 1.0 if executed_volume > 0 else 0.0
		return min(1.0, executed_volume / order_volume)

	@staticmethod
	def _calculate_timing_efficiency (
			order: Dict[str, Any],
			trades: List[Dict[str, Any]]
		) -> float:
		"""计算时机效率（基于成交时间分布）"""
		_ = order
		if not trades:
			return 0.0
		trade_times: List[pd.Timestamp] = []
		for t in trades:
			tt = t.get("trade_time")
			if tt is not None:
				try:
					trade_times.append(pd.Timestamp(tt))
				except (ValueError, TypeError):
					continue
		if len(trade_times) < 2:
			return 0.5
		time_span = (max(trade_times) - min(trade_times)).total_seconds()
		return max(0.0, min(1.0, 1.0 - time_span / 300))

	@staticmethod
	def _calculate_price_efficiency (
			order: Dict[str, Any],
			trades: List[Dict[str, Any]],
			market_data: Optional[Dict[str, Any]]
		) -> float:
		"""计算价格效率（相对限价的改进程度）"""
		_ = market_data
		if not trades:
			return 0.0
		order_price = float(order.get("price", order.get("limit_price", 0)))
		direction = order.get("direction", "buy")
		if order_price <= 0:
			return 0.5
		total_volume = 0
		weighted_improvement = 0.0
		for t in trades:
			tp = float(t.get("price", 0))
			tv = int(t.get("volume", 0))
			if direction in ("buy", "BUY"):
				improvement = (order_price - tp) / order_price
			else:
				improvement = (tp - order_price) / order_price
			weighted_improvement += improvement * tv
			total_volume += tv
		if total_volume == 0:
			return 0.5
		avg_improv = weighted_improvement / total_volume
		return max(0.0, min(1.0, 0.5 + avg_improv * 50))

	@staticmethod
	def _calculate_urgency_efficiency (
			order: Dict[str, Any],
			trades: List[Dict[str, Any]]
		) -> float:
		"""计算紧急度效率"""
		if not trades:
			return 0.0
		submitted_at = order.get("submitted_at")
		if submitted_at is None:
			return 0.5
		try:
			if isinstance(submitted_at, str):
				submitted_dt = pd.Timestamp(datetime.fromisoformat(submitted_at.replace("Z", "+00:00")))
			else:
				submitted_dt = pd.Timestamp(submitted_at)
		except (ValueError, TypeError):
			return 0.5
		first_trade_time = None
		for t in trades:
			tt = t.get("trade_time")
			if tt is not None:
				try:
					if isinstance(tt, str):
						ft = pd.Timestamp(datetime.fromisoformat(tt.replace("Z", "+00:00")))
					else:
						ft = pd.Timestamp(tt)
					if first_trade_time is None or ft < first_trade_time:
						first_trade_time = ft
				except (ValueError, TypeError):
					continue
		if first_trade_time is None:
			return 0.0
		delay = (first_trade_time - submitted_dt).total_seconds()
		return max(0.0, min(1.0, 1.0 - delay / 120))

	@staticmethod
	def _calculate_avg_execution_time (
			order: Dict[str, Any],
			trades: List[Dict[str, Any]]
		) -> Optional[float]:
		"""计算订单的平均执行时间"""
		submitted_at = order.get("submitted_at")
		if not submitted_at or not trades:
			return None
		try:
			if isinstance(submitted_at, str):
				submitted_dt = pd.Timestamp(datetime.fromisoformat(submitted_at.replace("Z", "+00:00")))
			else:
				submitted_dt = pd.Timestamp(submitted_at)
		except (ValueError, TypeError):
			return None
		deltas = []
		for t in trades:
			tt = t.get("trade_time")
			if tt is None:
				continue
			try:
				if isinstance(tt, str):
					trade_dt = pd.Timestamp(datetime.fromisoformat(tt.replace("Z", "+00:00")))
				else:
					trade_dt = pd.Timestamp(tt)
				deltas.append((trade_dt - submitted_dt).total_seconds())
			except (ValueError, TypeError):
				continue
		return float(np.mean(deltas)) if deltas else None

	@staticmethod
	def _calculate_avg_price_improvement (
			order: Dict[str, Any],
			trades: List[Dict[str, Any]]
		) -> Optional[float]:
		"""计算订单的平均价格改进"""
		order_price = float(order.get("price", order.get("limit_price", 0)))
		direction = order.get("direction", "buy")
		if order_price <= 0 or not trades:
			return None
		improvements = []
		for t in trades:
			tp = float(t.get("price", 0))
			if tp <= 0:
				continue
			if direction in ("buy", "BUY"):
				improvements.append(order_price - tp)
			else:
				improvements.append(tp - order_price)
		return float(np.mean(improvements)) if improvements else None

	@staticmethod
	def _calculate_overall_consistency (
			consistency_results: Dict[str, Dict[str, Any]]
		) -> Dict[str, Any]:
		"""计算整体执行一致性"""
		if not consistency_results:
			return {"overall_score": 0.0, "securities_analyzed": 0}
		scores = []
		for ts_code, metrics in consistency_results.items():
			score = metrics.get("consistency_score", 0)
			if score is not None:
				scores.append(score)
		return {
			"overall_score": float(np.mean(scores)) if scores else 0.0,
			"std_score": float(np.std(scores)) if scores else 0.0,
			"securities_analyzed": len(consistency_results),
			"high_consistency_count": int(np.sum(np.array(scores) > 0.7)) if scores else 0,
			"low_consistency_count": int(np.sum(np.array(scores) < 0.4)) if scores else 0,
		}

	@staticmethod
	def _calculate_quality_rating (
			execution_time: Dict[str, Any],
			fill_rate: Dict[str, Any],
			price_improvement: Dict[str, Any],
			execution_efficiency: Dict[str, Any]
		) -> str:
		"""计算执行质量综合评级"""
		time_stat = execution_time.get("statistics", {})
		avg_time = time_stat.get("mean", 300)
		time_score = max(0.0, 1.0 - float(avg_time) / 600) if avg_time else 0.5

		fill_stat = fill_rate.get("statistics", {})
		fill_score = fill_stat.get("mean_fill_rate", 0)

		pi_stat = price_improvement.get("statistics", {})
		pi_score = pi_stat.get("positive_improvement_rate", 0)

		eff_stat = execution_efficiency.get("statistics", {})
		eff_score = eff_stat.get("mean_composite", 0.5)

		composite = 0.15 * time_score + 0.30 * fill_score + 0.25 * pi_score + 0.30 * eff_score

		if composite >= 0.85:
			return "A"
		elif composite >= 0.70:
			return "B"
		elif composite >= 0.50:
			return "C"
		elif composite >= 0.30:
			return "D"
		else:
			return "F"