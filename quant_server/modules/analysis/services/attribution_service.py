#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归因分析服务

负责计算收益归因，包括Brinson归因、因子归因、行业归因等。
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.models import AttributionAnalysis
from modules.analysis.analyzers.attribution.factor_attribution import FactorAttribution
from shared.database.repositories.strategy_repo import StrategyRepository
from shared.database.repositories.account_repo import AccountRepository
from shared.database.repositories.position_repo import PositionRepository
from quant_server.shared.database.repositories.market.quote import StockDailyRepository
from shared.database.repositories.stock_repo import StockRepository
from core.utils.math_utils.statistic_calculator import StatisticCalculator


class AttributionService:
	"""归因分析服务"""

	def __init__ (
			self,
			session: AsyncSession,
			strategy_repo: StrategyRepository = None,
			account_repo: AccountRepository = None,
			position_repo: PositionRepository = None,
		quote_repo: StockDailyRepository = None,
			stock_repo: StockRepository = None
	):
		"""
		初始化归因服务

		Args:
			session: 数据库会话
			strategy_repo: 策略Repository
			account_repo: 账户Repository
			position_repo: 持仓Repository
			quote_repo: 行情Repository
			stock_repo: 股票Repository
		"""
		self.session = session
		self.strategy_repo = strategy_repo or StrategyRepository(session)
		self.account_repo = account_repo or AccountRepository(session)
		self.position_repo = position_repo or PositionRepository(session)
		self.quote_repo = quote_repo or StockDailyRepository(session)
		self.stock_repo = stock_repo or StockRepository(session)
		self.stat_calc = StatisticCalculator()
		self.factor_attributor = FactorAttribution()

	async def perform_brinson_attribution (
			self,
			portfolio_id: str,
			start_date: date,
			end_date: date,
			benchmark: str,
			sectors: List[str] = None
	) -> AttributionAnalysis:
		"""
		执行Brinson归因分析

		Args:
			portfolio_id: 组合ID（可以是策略ID或账户ID）
			start_date: 开始日期
			end_date: 结束日期
			benchmark: 基准代码
			sectors: 行业分类列表（可选）

		Returns:
			AttributionAnalysis: 归因分析结果
		"""
		try:
			# 获取组合持仓数据
			portfolio_positions = await self._get_portfolio_positions(
				portfolio_id, start_date, end_date
			)

			# 获取基准持仓数据
			benchmark_positions = await self._get_benchmark_positions(
				benchmark, start_date, end_date
			)

			if not portfolio_positions or not benchmark_positions:
				raise ValueError("持仓数据不足")

			# 计算总收益
			portfolio_return = await self._calculate_portfolio_return(
				portfolio_positions, start_date, end_date
			)

			benchmark_return = await self._calculate_benchmark_return(
				benchmark_positions, start_date, end_date
			)

			active_return = portfolio_return - benchmark_return

			# 执行Brinson归因
			if sectors:
				# 按行业进行归因
				attribution_results = await self._perform_sector_brinson(
					portfolio_positions, benchmark_positions,
					sectors, start_date, end_date
				)

				allocation_effect = attribution_results.get('allocation_effect', Decimal("0.0"))
				selection_effect = attribution_results.get('selection_effect', Decimal("0.0"))
				interaction_effect = attribution_results.get('interaction_effect', Decimal("0.0"))

				# 获取行业归因详情
				sector_attributions = attribution_results.get('sector_attributions', {})
				sector_allocations = attribution_results.get('sector_allocations', {})

				# 构建归因分析对象
				attribution = AttributionAnalysis(
					attribution_id=f"attr_{portfolio_id}_{start_date}_{end_date}",
					portfolio_id=portfolio_id,
					analysis_period=f"{start_date} 至 {end_date}",
					attribution_model="Brinson Sector Attribution",
					benchmark=benchmark,
					total_return=Decimal(str(portfolio_return)),
					benchmark_return=Decimal(str(benchmark_return)),
					active_return=Decimal(str(active_return)),
					allocation_effect=Decimal(str(allocation_effect)),
					selection_effect=Decimal(str(selection_effect)),
					interaction_effect=Decimal(str(interaction_effect)),
					sector_attributions=sector_attributions,
					sector_allocations=sector_allocations
				)
			else:
				# 按个股进行归因
				attribution_results = await self._perform_stock_brinson(
					portfolio_positions, benchmark_positions,
					start_date, end_date
				)

				allocation_effect = attribution_results.get('allocation_effect', Decimal("0.0"))
				selection_effect = attribution_results.get('selection_effect', Decimal("0.0"))
				interaction_effect = attribution_results.get('interaction_effect', Decimal("0.0"))

				# 获取个股归因详情
				stock_attributions = attribution_results.get('stock_attributions', {})
				stock_contributions = attribution_results.get('stock_contributions', {})

				# 构建归因分析对象
				attribution = AttributionAnalysis(
					attribution_id=f"attr_{portfolio_id}_{start_date}_{end_date}",
					portfolio_id=portfolio_id,
					analysis_period=f"{start_date} 至 {end_date}",
					attribution_model="Brinson Stock Attribution",
					benchmark=benchmark,
					total_return=Decimal(str(portfolio_return)),
					benchmark_return=Decimal(str(benchmark_return)),
					active_return=Decimal(str(active_return)),
					allocation_effect=Decimal(str(allocation_effect)),
					selection_effect=Decimal(str(selection_effect)),
					interaction_effect=Decimal(str(interaction_effect)),
					stock_attributions=stock_attributions,
					stock_contributions=stock_contributions
				)

			return attribution

		except Exception as e:
			raise ValueError(f"Brinson归因分析失败: {str(e)}")

	async def perform_factor_attribution (
			self,
			portfolio_id: str,
			start_date: date,
			end_date: date,
			factor_model: str = "Fama-French"
	) -> AttributionAnalysis:
		"""
		执行因子归因分析

		Args:
			portfolio_id: 组合ID
			start_date: 开始日期
			end_date: 结束日期
			factor_model: 因子模型 ('Fama-French', 'Carhart', 'Other')

		Returns:
			AttributionAnalysis: 因子归因结果
		"""
		try:
			# 获取组合收益序列
			portfolio_returns = await self._get_portfolio_returns(
				portfolio_id, start_date, end_date
			)

			if len(portfolio_returns) < 10:
				raise ValueError("收益数据不足")

			# 获取因子收益率
			factor_returns = await self._get_factor_returns(
				factor_model, start_date, end_date
			)

			if factor_returns.empty:
				raise ValueError(f"无法获取因子收益率: {factor_model}")

			# 使用FactorAttribution执行因子归因分析
			attribution_result = self.factor_attributor.perform_factor_attribution(
				portfolio_returns=portfolio_returns,
				factor_returns=factor_returns,
				factor_model=factor_model
			)

			# 计算总收益
			total_return = np.prod(1 + portfolio_returns.values) - 1

			# 构建归因分析对象
			attribution = AttributionAnalysis(
				attribution_id=f"factor_{portfolio_id}_{start_date}_{end_date}",
				portfolio_id=portfolio_id,
				analysis_period=f"{start_date} 至 {end_date}",
				attribution_model=f"Factor Attribution ({factor_model})",
				benchmark=None,
				total_return=Decimal(str(total_return)),
				factor_attributions={
					factor: Decimal(str(attr))
					for factor, attr in attribution_result['factor_contributions'].items()
				},
				factor_exposures={
					factor: Decimal(str(exposure))
					for factor, exposure in attribution_result['factor_exposures'].items()
				}
			)

			return attribution

		except Exception as e:
			raise ValueError(f"因子归因分析失败: {str(e)}")

	async def compare_attribution_models (
			self,
			portfolio_id: str,
			start_date: date,
			end_date: date,
			benchmark: str = None
	) -> Dict[str, AttributionAnalysis]:
		"""
		比较不同归因模型的结果

		Args:
			portfolio_id: 组合ID
			start_date: 开始日期
			end_date: 结束日期
			benchmark: 基准代码

		Returns:
			不同模型的归因结果字典
		"""
		results = {}

		# Brinson归因
		if benchmark:
			try:
				brinson_result = await self.perform_brinson_attribution(
					portfolio_id, start_date, end_date, benchmark
				)
				results['brinson'] = brinson_result
			except Exception as e:
				print(f"Brinson归因失败: {str(e)}")

		# 因子归因
		for factor_model in ['Fama-French', 'Carhart']:
			try:
				factor_result = await self.perform_factor_attribution(
					portfolio_id, start_date, end_date, factor_model
				)
				results[factor_model.lower()] = factor_result
			except Exception as e:
				print(f"{factor_model}因子归因失败: {str(e)}")

		return results

	async def _get_portfolio_positions (
			self,
			portfolio_id: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取组合持仓数据

		Args:
			portfolio_id: 组合ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			持仓数据列表
		"""
		# 判断是策略还是账户
		if portfolio_id.startswith('strategy_'):
			positions = await self.strategy_repo.get_positions(
				portfolio_id, start_date, end_date
			)
		else:
			positions = await self.account_repo.get_positions(
				int(portfolio_id), start_date, end_date
			)

		return positions

	async def _get_benchmark_positions (
			self,
			benchmark: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取基准持仓数据

		Args:
			benchmark: 基准代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			基准持仓数据
		"""
		# 简化实现：对于指数基准，获取成分股权重
		if benchmark == '000300.SH':  # 沪深300
			# 获取沪深300成分股和权重
			return await self._get_hs300_constituents(start_date)
		elif benchmark == '000905.SH':  # 中证500
			return await self._get_zz500_constituents(start_date)
		else:
			# 默认实现
			return []

	async def _calculate_portfolio_return (
			self,
			positions: List[Dict[str, Any]],
			start_date: date,
			end_date: date
	) -> float:
		"""
		计算组合收益率

		Args:
			positions: 持仓数据
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			组合收益率
		"""
		if not positions:
			return 0.0

		# 简化实现：加权平均计算
		total_return = 0.0
		total_weight = 0.0

		for position in positions:
			ts_code = position.get('ts_code')
			weight = position.get('weight', 0.0)

			if ts_code and weight > 0:
				# 获取股票收益率
				stock_return = await self._get_stock_return(
					ts_code, start_date, end_date
				)

				total_return += stock_return * weight
				total_weight += weight

		if total_weight > 0:
			return total_return / total_weight
		else:
			return 0.0

	async def _perform_sector_brinson (
			self,
			portfolio_positions: List[Dict[str, Any]],
			benchmark_positions: List[Dict[str, Any]],
			sectors: List[str],
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		执行按行业的Brinson归因

		Args:
			portfolio_positions: 组合持仓
			benchmark_positions: 基准持仓
			sectors: 行业列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			行业归因结果
		"""
		# 简化实现
		return {
			'allocation_effect': 0.02,
			'selection_effect': 0.015,
			'interaction_effect': 0.005,
			'sector_attributions': {sector: 0.01 for sector in sectors},
			'sector_allocations': {sector: 0.5 for sector in sectors}
		}

	async def _get_factor_returns (
			self,
			factor_model: str,
			start_date: date,
			end_date: date
	) -> pd.DataFrame:
		"""
		获取因子收益率数据

		Args:
			factor_model: 因子模型
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			因子收益率DataFrame
		"""
		# 简化实现：返回模拟数据
		dates = pd.date_range(start_date, end_date, freq='D')

		if factor_model == 'Fama-French':
			factors = ['MKT', 'SMB', 'HML']
		elif factor_model == 'Carhart':
			factors = ['MKT', 'SMB', 'HML', 'UMD']
		else:
			factors = ['Factor1', 'Factor2', 'Factor3']

		np.random.seed(42)
		data = np.random.randn(len(dates), len(factors)) * 0.01

		return pd.DataFrame(data, index=dates, columns=factors)

	async def _perform_factor_regression (
			self,
			portfolio_returns: np.ndarray,
			factor_returns: np.ndarray,
			factor_names: List[str]
	) -> Tuple[Dict[str, float], Dict[str, float]]:
		"""
		执行因子回归

		Args:
			portfolio_returns: 组合收益率
			factor_returns: 因子收益率
			factor_names: 因子名称

		Returns:
			(因子暴露度, 因子归因贡献)
		"""
		# 使用OLS回归
		from sklearn.linear_model import LinearRegression

		if len(portfolio_returns) != len(factor_returns):
			raise ValueError("收益率序列长度不匹配")

		# 添加截距项
		X = np.column_stack([np.ones(len(factor_returns)), factor_returns])

		# 拟合模型
		model = LinearRegression()
		model.fit(X, portfolio_returns)

		# 获取因子暴露
		exposures = {}
		for i, factor in enumerate(factor_names):
			exposures[factor] = model.coef_[i + 1]  # 跳过截距

		# 计算因子贡献
		attributions = {}
		for i, factor in enumerate(factor_names):
			factor_contribution = model.coef_[i + 1] * np.mean(factor_returns[:, i])
			attributions[factor] = factor_contribution

		return exposures, attributions