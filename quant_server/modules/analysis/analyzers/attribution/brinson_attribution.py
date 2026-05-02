#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Brinson归因分析器

负责执行Brinson模型归因分析，将超额收益分解为配置效应和选择效应。
"""

from datetime import date
from typing import Dict, List, Optional, Any



class BrinsonAttribution:
	"""Brinson归因分析器"""

	def __init__ (self):
		"""初始化Brinson归因分析器"""

	def perform_brinson_attribution (
			self,
			portfolio_weights: Dict[str, float],
			portfolio_returns: Dict[str, float],
			benchmark_weights: Dict[str, float],
			benchmark_returns: Dict[str, float],
			sectors: Optional[Dict[str, List[str]]] = None
	) -> Dict[str, Any]:
		"""
		执行Brinson归因分析

		Args:
			portfolio_weights: 组合权重 {资产代码: 权重}
			portfolio_returns: 组合收益 {资产代码: 收益率}
			benchmark_weights: 基准权重 {资产代码: 权重}
			benchmark_returns: 基准收益 {资产代码: 收益率}
			sectors: 行业分类 {行业名称: [资产代码列表]}（可选）

		Returns:
			Brinson归因结果
		"""
		try:
			# 验证输入数据
			self._validate_inputs(portfolio_weights, portfolio_returns,
			                      benchmark_weights, benchmark_returns)

			# 计算基准收益
			benchmark_total_return = self._calculate_total_return(
				benchmark_weights, benchmark_returns
			)

			# 计算组合收益
			portfolio_total_return = self._calculate_total_return(
				portfolio_weights, portfolio_returns
			)

			# 计算超额收益
			active_return = portfolio_total_return - benchmark_total_return

			if sectors:
				# 行业级别的Brinson归因
				attribution_results = self._perform_sector_brinson(
					portfolio_weights, portfolio_returns,
					benchmark_weights, benchmark_returns,
					sectors
				)
			else:
				# 资产级别的Brinson归因
				attribution_results = self._perform_asset_brinson(
					portfolio_weights, portfolio_returns,
					benchmark_weights, benchmark_returns
				)

			# 添加汇总信息
			attribution_results.update({
				'portfolio_return': portfolio_total_return,
				'benchmark_return': benchmark_total_return,
				'active_return': active_return,
				'attribution_model': 'Brinson'
			})

			return attribution_results

		except Exception as e:
			raise ValueError(f"Brinson归因分析失败: {str(e)}")

	def perform_multiperiod_brinson (
			self,
			portfolio_data: List[Dict[str, Any]],
			benchmark_data: List[Dict[str, Any]],
			frequency: str = 'daily'
	) -> Dict[str, Any]:
		"""
		执行多期Brinson归因分析

		Args:
			portfolio_data: 多期组合数据列表
			benchmark_data: 多期基准数据列表
			frequency: 数据频率 ('daily', 'weekly', 'monthly')

		Returns:
			多期Brinson归因结果
		"""
		try:
			if len(portfolio_data) != len(benchmark_data):
				raise ValueError("组合数据和基准数据期数不一致")

			if len(portfolio_data) < 2:
				raise ValueError("需要至少两期数据")

			# 按时期进行归因
			period_attributions = []
			cumulative_attribution = {
				'allocation_effect': 0.0,
				'selection_effect': 0.0,
				'interaction_effect': 0.0
			}

			for i in range(len(portfolio_data)):
				if i == 0:
					continue  # 跳过第一期，因为没有前一期的比较

				# 提取当期数据
				portfolio_weights = portfolio_data[i].get('weights', {})
				portfolio_returns = portfolio_data[i].get('returns', {})
				benchmark_weights = benchmark_data[i].get('weights', {})
				benchmark_returns = benchmark_data[i].get('returns', {})

				# 执行单期归因
				period_result = self._perform_asset_brinson(
					portfolio_weights, portfolio_returns,
					benchmark_weights, benchmark_returns
				)

				period_attributions.append({
					'period': i,
					'allocation_effect': period_result['allocation_effect'],
					'selection_effect': period_result['selection_effect'],
					'interaction_effect': period_result['interaction_effect']
				})

				# 累积效应
				cumulative_attribution['allocation_effect'] += period_result['allocation_effect']
				cumulative_attribution['selection_effect'] += period_result['selection_effect']
				cumulative_attribution['interaction_effect'] += period_result['interaction_effect']

			# 计算总收益
			first_portfolio = portfolio_data[0]
			last_portfolio = portfolio_data[-1]
			first_benchmark = benchmark_data[0]
			last_benchmark = benchmark_data[-1]

			portfolio_total_return = self._calculate_multiperiod_return(
				first_portfolio, last_portfolio
			)
			benchmark_total_return = self._calculate_multiperiod_return(
				first_benchmark, last_benchmark
			)
			active_return = portfolio_total_return - benchmark_total_return

			# 验证归因一致性
			attribution_sum = (
					cumulative_attribution['allocation_effect'] +
					cumulative_attribution['selection_effect'] +
					cumulative_attribution['interaction_effect']
			)

			attribution_error = active_return - attribution_sum

			return {
				'period_attributions': period_attributions,
				'cumulative_attribution': cumulative_attribution,
				'portfolio_return': portfolio_total_return,
				'benchmark_return': benchmark_total_return,
				'active_return': active_return,
				'attribution_error': attribution_error,
				'frequency': frequency,
				'num_periods': len(portfolio_data) - 1
			}

		except Exception as e:
			raise ValueError(f"多期Brinson归因失败: {str(e)}")

	def calculate_brinson_with_interaction (
			self,
			portfolio_weights: Dict[str, float],
			portfolio_returns: Dict[str, float],
			benchmark_weights: Dict[str, float],
			benchmark_returns: Dict[str, float],
			include_interaction: bool = True
	) -> Dict[str, float]:
		"""
		计算Brinson归因（可选择是否包含交互效应）

		Args:
			portfolio_weights: 组合权重
			portfolio_returns: 组合收益
			benchmark_weights: 基准权重
			benchmark_returns: 基准收益
			include_interaction: 是否包含交互效应

		Returns:
			归因效应分解
		"""
		try:
			# 计算总收益
			portfolio_return = self._calculate_total_return(portfolio_weights, portfolio_returns)
			benchmark_return = self._calculate_total_return(benchmark_weights, benchmark_returns)

			# 获取所有资产
			all_assets = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

			# 初始化效应
			allocation_effect = 0.0
			selection_effect = 0.0
			interaction_effect = 0.0

			for asset in all_assets:
				w_p = portfolio_weights.get(asset, 0.0)
				w_b = benchmark_weights.get(asset, 0.0)
				r_p = portfolio_returns.get(asset, 0.0)
				r_b = benchmark_returns.get(asset, 0.0)

				# 配置效应: (w_p - w_b) * r_b
				allocation_effect += (w_p - w_b) * r_b

				# 选择效应: w_b * (r_p - r_b)
				selection_effect += w_b * (r_p - r_b)

				# 交互效应: (w_p - w_b) * (r_p - r_b)
				if include_interaction:
					interaction_effect += (w_p - w_b) * (r_p - r_b)

			# 验证结果
			total_effect = allocation_effect + selection_effect + interaction_effect
			active_return = portfolio_return - benchmark_return

			# 计算归因误差
			attribution_error = active_return - total_effect

			return {
				'allocation_effect': allocation_effect,
				'selection_effect': selection_effect,
				'interaction_effect': interaction_effect,
				'total_effect': total_effect,
				'portfolio_return': portfolio_return,
				'benchmark_return': benchmark_return,
				'active_return': active_return,
				'attribution_error': attribution_error
			}

		except Exception as e:
			raise ValueError(f"Brinson归因计算失败: {str(e)}")

	@staticmethod
	def _validate_inputs (
			portfolio_weights: Dict[str, float],
			portfolio_returns: Dict[str, float],
			benchmark_weights: Dict[str, float],
			benchmark_returns: Dict[str, float]
	):
		"""验证输入数据"""
		# 检查权重和为1（允许微小误差）
		portfolio_weight_sum = sum(portfolio_weights.values())
		benchmark_weight_sum = sum(benchmark_weights.values())

		if abs(portfolio_weight_sum - 1.0) > 0.01:
			raise ValueError(f"组合权重和不为1: {portfolio_weight_sum}")

		if abs(benchmark_weight_sum - 1.0) > 0.01:
			raise ValueError(f"基准权重和不为1: {benchmark_weight_sum}")

		# 检查数据一致性
		portfolio_assets = set(portfolio_weights.keys()) | set(portfolio_returns.keys())
		benchmark_assets = set(benchmark_weights.keys()) | set(benchmark_returns.keys())

		if len(portfolio_assets) == 0:
			raise ValueError("组合数据为空")

		if len(benchmark_assets) == 0:
			raise ValueError("基准数据为空")

	@staticmethod
	def _calculate_total_return (
			weights: Dict[str, float],
			returns: Dict[str, float]
	) -> float:
		"""计算加权总收益"""
		total_return = 0.0

		for asset, weight in weights.items():
			asset_return = returns.get(asset, 0.0)
			total_return += weight * asset_return

		return total_return

	def _perform_sector_brinson (
			self,
			portfolio_weights: Dict[str, float],
			portfolio_returns: Dict[str, float],
			benchmark_weights: Dict[str, float],
			benchmark_returns: Dict[str, float],
			sectors: Dict[str, List[str]]
	) -> Dict[str, Any]:
		"""执行行业级别Brinson归因"""
		# 计算行业权重和收益
		sector_portfolio_weights = {}
		sector_portfolio_returns = {}
		sector_benchmark_weights = {}
		sector_benchmark_returns = {}

		for sector, assets in sectors.items():
			# 计算行业权重
			w_p_sector = sum(portfolio_weights.get(asset, 0.0) for asset in assets)
			w_b_sector = sum(benchmark_weights.get(asset, 0.0) for asset in assets)

			# 计算行业收益（加权平均）
			if w_p_sector > 0:
				r_p_sector = sum(
					portfolio_weights.get(asset, 0.0) * portfolio_returns.get(asset, 0.0)
					for asset in assets
				) / w_p_sector
			else:
				r_p_sector = 0.0

			if w_b_sector > 0:
				r_b_sector = sum(
					benchmark_weights.get(asset, 0.0) * benchmark_returns.get(asset, 0.0)
					for asset in assets
				) / w_b_sector
			else:
				r_b_sector = 0.0

			sector_portfolio_weights[sector] = w_p_sector
			sector_portfolio_returns[sector] = r_p_sector
			sector_benchmark_weights[sector] = w_b_sector
			sector_benchmark_returns[sector] = r_b_sector

		# 在行业级别执行Brinson归因
		sector_attribution = self._perform_asset_brinson(
			sector_portfolio_weights, sector_portfolio_returns,
			sector_benchmark_weights, sector_benchmark_returns
		)

		# 计算行业内的选择效应（二级归因）
		within_sector_selection = {}

		for sector, assets in sectors.items():
			sector_selection = 0.0

			for asset in assets:
				w_b_asset = benchmark_weights.get(asset, 0.0)
				w_p_asset = portfolio_weights.get(asset, 0.0)
				r_p_asset = portfolio_returns.get(asset, 0.0)
				r_b_asset = benchmark_returns.get(asset, 0.0)

				# 行业内的选择效应
				if sector_benchmark_weights[sector] > 0:
					# 标准化权重
					w_b_asset_normalized = w_b_asset / sector_benchmark_weights[sector]
					selection_effect = w_b_asset_normalized * (r_p_asset - r_b_asset)
					sector_selection += selection_effect

			within_sector_selection[sector] = sector_selection

		# 整合结果
		return {
			'allocation_effect': sector_attribution['allocation_effect'],
			'selection_effect': sector_attribution['selection_effect'],
			'interaction_effect': sector_attribution['interaction_effect'],
			'sector_allocation_effects': sector_attribution.get('asset_allocation_effects', {}),
			'within_sector_selection': within_sector_selection,
			'sector_weights': {
				'portfolio': sector_portfolio_weights,
				'benchmark': sector_benchmark_weights
			},
			'sector_returns': {
				'portfolio': sector_portfolio_returns,
				'benchmark': sector_benchmark_returns
			}
		}

	@staticmethod
	def _perform_asset_brinson (
			portfolio_weights: Dict[str, float],
			portfolio_returns: Dict[str, float],
			benchmark_weights: Dict[str, float],
			benchmark_returns: Dict[str, float]
	) -> Dict[str, Any]:
		"""执行资产级别Brinson归因"""
		# 获取所有资产
		all_assets = set(portfolio_weights.keys()) | set(portfolio_returns.keys()) | \
		             set(benchmark_weights.keys()) | set(benchmark_returns.keys())

		# 初始化效应
		allocation_effect = 0.0
		selection_effect = 0.0
		interaction_effect = 0.0

		# 存储每个资产的贡献
		asset_allocation_effects = {}
		asset_selection_effects = {}
		asset_interaction_effects = {}

		for asset in all_assets:
			w_p = portfolio_weights.get(asset, 0.0)
			w_b = benchmark_weights.get(asset, 0.0)
			r_p = portfolio_returns.get(asset, 0.0)
			r_b = benchmark_returns.get(asset, 0.0)

			# 配置效应
			allocation = (w_p - w_b) * r_b
			allocation_effect += allocation
			asset_allocation_effects[asset] = allocation

			# 选择效应
			selection = w_b * (r_p - r_b)
			selection_effect += selection
			asset_selection_effects[asset] = selection

			# 交互效应
			interaction = (w_p - w_b) * (r_p - r_b)
			interaction_effect += interaction
			asset_interaction_effects[asset] = interaction

		return {
			'allocation_effect': allocation_effect,
			'selection_effect': selection_effect,
			'interaction_effect': interaction_effect,
			'asset_allocation_effects': asset_allocation_effects,
			'asset_selection_effects': asset_selection_effects,
			'asset_interaction_effects': asset_interaction_effects
		}

	@staticmethod
	def _calculate_multiperiod_return (
			start_data: Dict[str, Any],
			end_data: Dict[str, Any]
	) -> float:
		"""计算多期总收益"""
		# 简化实现：假设数据已经包含累计收益
		start_value = start_data.get('total_value', 1.0)
		end_value = end_data.get('total_value', 1.0)

		if start_value == 0:
			return 0.0

		return (end_value - start_value) / start_value

	def calculate_brinson_fach_attribution (
			self,
			portfolio_weights: List[Dict[str, float]],
			portfolio_returns: List[Dict[str, float]],
			benchmark_weights: List[Dict[str, float]],
			benchmark_returns: List[Dict[str, float]]
	) -> Dict[str, Any]:
		"""
		执行Fach修正的Brinson归因（处理多期数据）

		Args:
			portfolio_weights: 多期组合权重
			portfolio_returns: 多期组合收益
			benchmark_weights: 多期基准权重
			benchmark_returns: 多期基准收益

		Returns:
			Fach修正的Brinson归因结果
		"""
		try:
			if len(portfolio_weights) != len(portfolio_returns) or \
					len(benchmark_weights) != len(benchmark_returns) or \
					len(portfolio_weights) != len(benchmark_weights):
				raise ValueError("输入数据期数不一致")

			n_periods = len(portfolio_weights)

			if n_periods < 2:
				raise ValueError("需要至少两期数据")

			# Fach归因公式
			total_allocation = 0.0
			total_selection = 0.0
			total_interaction = 0.0

			for t in range(n_periods):
				# 获取当期和前一期数据
				if t == 0:
					w_p_prev = portfolio_weights[t]
					w_b_prev = benchmark_weights[t]
				else:
					w_p_prev = portfolio_weights[t - 1]
					w_b_prev = benchmark_weights[t - 1]

				w_p_curr = portfolio_weights[t]
				w_b_curr = benchmark_weights[t]
				r_p_curr = portfolio_returns[t]
				r_b_curr = benchmark_returns[t]

				# 获取所有资产
				all_assets = set(w_p_prev.keys()) | set(w_b_prev.keys()) | \
				             set(w_p_curr.keys()) | set(w_b_curr.keys()) | \
				             set(r_p_curr.keys()) | set(r_b_curr.keys())

				for asset in all_assets:
					w_p_prev_asset = w_p_prev.get(asset, 0.0)
					w_b_prev_asset = w_b_prev.get(asset, 0.0)
					w_p_curr_asset = w_p_curr.get(asset, 0.0)
					w_b_curr_asset = w_b_curr.get(asset, 0.0)
					r_p_curr_asset = r_p_curr.get(asset, 0.0)
					r_b_curr_asset = r_b_curr.get(asset, 0.0)

					# Fach配置效应公式
					allocation = (
							(w_p_prev_asset - w_b_prev_asset) * r_b_curr_asset +
							(w_p_curr_asset - w_p_prev_asset) * (r_b_curr_asset - r_b_curr_asset) / 2
					)

					# Fach选择效应公式
					selection = (
							w_b_prev_asset * (r_p_curr_asset - r_b_curr_asset) +
							(w_b_curr_asset - w_b_prev_asset) * (r_p_curr_asset - r_b_curr_asset) / 2
					)

					# Fach交互效应公式
					interaction = (
							(w_p_prev_asset - w_b_prev_asset) * (r_p_curr_asset - r_b_curr_asset) +
							((w_p_curr_asset - w_p_prev_asset) - (w_b_curr_asset - w_b_prev_asset)) *
							(r_p_curr_asset - r_b_curr_asset) / 2
					)

					total_allocation += allocation
					total_selection += selection
					total_interaction += interaction

			# 计算总收益
			portfolio_total_return = self._calculate_multiperiod_total_return(
				portfolio_weights, portfolio_returns
			)
			benchmark_total_return = self._calculate_multiperiod_total_return(
				benchmark_weights, benchmark_returns
			)
			active_return = portfolio_total_return - benchmark_total_return

			return {
				'allocation_effect': total_allocation,
				'selection_effect': total_selection,
				'interaction_effect': total_interaction,
				'portfolio_return': portfolio_total_return,
				'benchmark_return': benchmark_total_return,
				'active_return': active_return,
				'attribution_model': 'Brinson-Fach',
				'num_periods': n_periods
			}

		except Exception as e:
			raise ValueError(f"Fach修正Brinson归因失败: {str(e)}")

	def _calculate_multiperiod_total_return (
			self,
			weights_list: List[Dict[str, float]],
			returns_list: List[Dict[str, float]]
	) -> float:
		"""计算多期总收益（复利）"""
		if len(weights_list) != len(returns_list):
			raise ValueError("权重和收益数据期数不一致")

		if len(weights_list) == 0:
			return 0.0

		cumulative_return = 1.0

		for t in range(len(weights_list)):
			period_return = self._calculate_total_return(
				weights_list[t], returns_list[t]
			)
			cumulative_return *= (1 + period_return)

		return cumulative_return - 1.0

	@staticmethod
	def create_attribution_report (
			attribution_results: Dict[str, Any],
			portfolio_name: str = "组合",
			benchmark_name: str = "基准"
	) -> Dict[str, Any]:
		"""
		创建归因报告

		Args:
			attribution_results: 归因分析结果
			portfolio_name: 组合名称
			benchmark_name: 基准名称

		Returns:
			格式化后的归因报告
		"""
		try:
			report = {
				'summary': {
					'portfolio_return': attribution_results.get('portfolio_return', 0.0),
					'benchmark_return': attribution_results.get('benchmark_return', 0.0),
					'active_return': attribution_results.get('active_return', 0.0),
					'allocation_effect': attribution_results.get('allocation_effect', 0.0),
					'selection_effect': attribution_results.get('selection_effect', 0.0),
					'interaction_effect': attribution_results.get('interaction_effect', 0.0),
					'attribution_error': attribution_results.get('attribution_error', 0.0)
				},
				'portfolio_name': portfolio_name,
				'benchmark_name': benchmark_name,
				'attribution_model': attribution_results.get('attribution_model', 'Brinson'),
				'analysis_date': date.today().isoformat()
			}

			# 添加详细效应分解
			if 'asset_allocation_effects' in attribution_results:
				report['detailed_allocation'] = attribution_results['asset_allocation_effects']

			if 'asset_selection_effects' in attribution_results:
				report['detailed_selection'] = attribution_results['asset_selection_effects']

			if 'asset_interaction_effects' in attribution_results:
				report['detailed_interaction'] = attribution_results['asset_interaction_effects']

			# 计算贡献百分比
			active_return = attribution_results.get('active_return', 0.0)
			if active_return != 0:
				report['contribution_percentages'] = {
					'allocation': attribution_results.get('allocation_effect', 0.0) / active_return * 100,
					'selection': attribution_results.get('selection_effect', 0.0) / active_return * 100,
					'interaction': attribution_results.get('interaction_effect', 0.0) / active_return * 100
				}

			return report

		except Exception as e:
			raise ValueError(f"创建归因报告失败: {str(e)}")
