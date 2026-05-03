#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风险分析器

负责计算和分析各种风险指标，包括波动率、最大回撤、在险价值等。
"""

import warnings
from datetime import date
from decimal import Decimal
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import pandas as pd
from scipy import stats

from modules.analysis.models import RiskMetrics


class RiskAnalyzer:
	"""风险分析器"""

	def __init__ (self, confidence_level: float = 0.95):
		"""
		初始化风险分析器

		Args:
			confidence_level: 置信水平（默认95%）
		"""
		self.confidence_level = confidence_level

	def analyze_risk_metrics (
			self,
			equity_curve: List[Dict[str, Any]],
			portfolio_positions: Optional[List[Dict[str, Any]]] = None,
			benchmark_returns: Optional[pd.Series] = None
	) -> RiskMetrics:
		"""
		分析风险指标

		Args:
			equity_curve: 净值曲线数据
			portfolio_positions: 组合持仓数据（可选）
			benchmark_returns: 基准收益率序列（可选）

		Returns:
			RiskMetrics: 风险指标对象
		"""
		try:
			if not equity_curve or len(equity_curve) < 10:
				raise ValueError("净值曲线数据不足")

			# 转换为DataFrame
			df = pd.DataFrame(equity_curve)
			df['date'] = pd.to_datetime(df['date'])
			df.set_index('date', inplace=True)

			# 确保数据按日期排序
			df = df.sort_index()

			# 计算收益率序列
			returns = df['equity'].pct_change().dropna()

			# 计算波动率指标
			volatility_metrics = self._calculate_volatility_metrics(returns)

			# 计算在险价值（VaR）
			var_metrics = self._calculate_var_metrics(returns)

			# 计算条件在险价值（CVaR/ES）
			cvar_metrics = self._calculate_cvar_metrics(returns)

			# 如果有持仓数据，计算集中度风险
			concentration_metrics = {}
			if portfolio_positions:
				concentration_metrics = self.analyze_concentration_risk(portfolio_positions)

			# 如果有基准数据，计算相对风险指标
			relative_risk_metrics = {}
			if benchmark_returns is not None:
				relative_risk_metrics = self._calculate_relative_risk_metrics(returns, benchmark_returns)

			# 构建风险指标对象
			risk_metrics = RiskMetrics(
				portfolio_id="default",
				analysis_date=date.today(),
				confidence_level=Decimal(str(self.confidence_level)),
				historical_volatility=Decimal(str(volatility_metrics['historical_volatility'])),
				realized_volatility=Decimal(str(volatility_metrics['realized_volatility'])),
				var_historical=Decimal(str(var_metrics['historical'])),
				var_parametric=Decimal(str(var_metrics['parametric'])),
				var_monte_carlo=Decimal(str(var_metrics['monte_carlo'])),
				conditional_var=Decimal(str(cvar_metrics['cvar'])),
				concentration_metrics=concentration_metrics,
				portfolio_beta=Decimal(str(relative_risk_metrics.get('beta', 0.0)))
			)

			# 添加额外数据
			risk_metrics.stress_test_results = self._perform_stress_tests(returns)
			risk_metrics.liquidity_metrics = self._estimate_liquidity_metrics(portfolio_positions)
			risk_metrics.correlation_matrix = self._calculate_correlation_matrix(portfolio_positions)
			risk_metrics.risk_contributions = self._calculate_risk_contributions(portfolio_positions)

			return risk_metrics

		except Exception as e:
			raise ValueError(f"风险分析失败: {str(e)}")

	def calculate_value_at_risk (
			self,
			returns: pd.Series,
			confidence_level: float = None,
			methods: List[str] = None
	) -> Dict[str, float]:
		"""
		计算在险价值（VaR）

		Args:
			returns: 收益率序列
			confidence_level: 置信水平
			methods: 计算方法列表

		Returns:
			不同方法的VaR结果
		"""
		if confidence_level is None:
			confidence_level = self.confidence_level

		if methods is None:
			methods = ['historical', 'parametric', 'monte_carlo']

		try:
			if len(returns) < 10:
				raise ValueError("收益率数据不足")

			var_results = {}

			for method in methods:
				if method == 'historical':
					var_results['historical'] = self._calculate_historical_var(returns, confidence_level)

				elif method == 'parametric':
					var_results['parametric'] = self._calculate_parametric_var(returns, confidence_level)

				elif method == 'monte_carlo':
					var_results['monte_carlo'] = self._calculate_monte_carlo_var(returns, confidence_level)

				elif method == 'modified':
					var_results['modified'] = self._calculate_modified_var(returns, confidence_level)

			return var_results

		except Exception as e:
			raise ValueError(f"VaR计算失败: {str(e)}")

	def calculate_expected_shortfall (
			self,
			returns: pd.Series,
			confidence_level: float = None,
			method: str = 'historical'
	) -> float:
		"""
		计算预期损失（ES/CVaR）

		Args:
			returns: 收益率序列
			confidence_level: 置信水平
			method: 计算方法

		Returns:
			预期损失值
		"""
		if confidence_level is None:
			confidence_level = self.confidence_level

		try:
			if method == 'historical':
				return self._calculate_historical_es(returns, confidence_level)
			elif method == 'parametric':
				return self._calculate_parametric_es(returns, confidence_level)
			elif method == 'monte_carlo':
				return self._calculate_monte_carlo_es(returns, confidence_level)
			else:
				raise ValueError(f"不支持的ES计算方法: {method}")

		except Exception as e:
			raise ValueError(f"ES计算失败: {str(e)}")

	def analyze_max_drawdown (
			self,
			equity_values: np.ndarray,
			detailed: bool = True
	) -> Dict[str, Any]:
		"""
		分析最大回撤

		Args:
			equity_values: 净值序列
			detailed: 是否返回详细信息

		Returns:
			最大回撤分析结果
		"""
		try:
			if len(equity_values) < 2:
				raise ValueError("净值数据不足")

			# 计算最大回撤
			max_drawdown, drawdown_duration, recovery_time = self._calculate_max_drawdown_details(equity_values)

			# 计算回撤统计数据
			drawdown_stats = self._calculate_drawdown_statistics(equity_values)

			result = {
				'max_drawdown': float(max_drawdown),
				'max_drawdown_period': drawdown_duration,
				'recovery_time': recovery_time,
				'drawdown_count': drawdown_stats['count'],
				'average_drawdown': drawdown_stats['average'],
				'drawdown_frequency': drawdown_stats['frequency']
			}

			if detailed:
				# 计算滚动最大回撤
				rolling_drawdowns = self._calculate_rolling_drawdowns(equity_values)
				result['rolling_drawdowns'] = rolling_drawdowns

				# 识别主要回撤期
				major_drawdowns = self._identify_major_drawdowns(equity_values)
				result['major_drawdowns'] = major_drawdowns

			return result

		except Exception as e:
			raise ValueError(f"最大回撤分析失败: {str(e)}")

	def perform_stress_test (
			self,
			returns: pd.Series,
			stress_scenarios: Dict[str, float] = None
	) -> Dict[str, float]:
		"""
		执行压力测试

		Args:
			returns: 收益率序列
			stress_scenarios: 压力场景

		Returns:
			压力测试结果
		"""
		if stress_scenarios is None:
			# 默认压力场景
			stress_scenarios = {
				'market_crash_2008': -0.05,  # 单日下跌5%
				'flash_crash_2010': -0.09,  # 单日下跌9%
				'covid_crash_2020': -0.08,  # 单日下跌8%
				'two_sigma_down': -2 * returns.std(),  # 两倍标准差下跌
				'three_sigma_down': -3 * returns.std()  # 三倍标准差下跌
			}

		try:
			stress_results = {}

			for scenario_name, stress_shock in stress_scenarios.items():
				# 应用压力冲击
				stressed_returns = returns + stress_shock

				# 计算压力下的VaR
				stressed_var = self._calculate_historical_var(stressed_returns, self.confidence_level)

				# 计算压力下的ES
				stressed_es = self._calculate_historical_es(stressed_returns, self.confidence_level)

				stress_results[scenario_name] = {
					'var_impact': float(stressed_var),
					'es_impact': float(stressed_es),
					'shock_size': float(stress_shock)
				}

			return stress_results

		except Exception as e:
			raise ValueError(f"压力测试失败: {str(e)}")

	def analyze_concentration_risk (
			self,
			portfolio_positions: List[Dict[str, Any]]
	) -> Dict[str, float]:
		"""
		分析集中度风险

		Args:
			portfolio_positions: 组合持仓数据

		Returns:
			集中度风险指标
		"""
		try:
			if not portfolio_positions:
				return {}

			# 计算总市值
			total_value = sum(pos.get('market_value', 0) for pos in portfolio_positions)

			if total_value == 0:
				return {}

			# 计算个股权重
			weights = []
			for position in portfolio_positions:
				weight = position.get('market_value', 0) / total_value
				weights.append(weight)

			weights = np.array(weights)

			# Herfindahl-Hirschman Index (HHI)
			hhi = np.sum(weights ** 2)

			# Concentration Ratio (CR)
			sorted_weights = np.sort(weights)[::-1]
			cr1 = sorted_weights[0] if len(sorted_weights) > 0 else 0
			cr3 = np.sum(sorted_weights[:3]) if len(sorted_weights) >= 3 else np.sum(sorted_weights)
			cr5 = np.sum(sorted_weights[:5]) if len(sorted_weights) >= 5 else np.sum(sorted_weights)

			# Gini Coefficient
			gini = self._calculate_gini_coefficient(weights)

			# Entropy Index
			entropy = self._calculate_entropy_index(weights)

			# 计算行业集中度（如果有行业信息）
			sector_concentration = self._calculate_sector_concentration(portfolio_positions)

			return {
				'hhi': float(hhi),
				'cr1': float(cr1),
				'cr3': float(cr3),
				'cr5': float(cr5),
				'gini_coefficient': float(gini),
				'entropy_index': float(entropy),
				'effective_number': float(1 / hhi) if hhi > 0 else 0,
				'sector_concentration': sector_concentration
			}

		except Exception as e:
			raise ValueError(f"集中度风险分析失败: {str(e)}")

	def calculate_liquidity_metrics (
			self,
			positions: List[Dict[str, Any]],
			market_data: Optional[Dict[str, Any]] = None
	) -> Dict[str, float]:
		"""
		计算流动性风险指标

		Args:
			positions: 持仓数据
			market_data: 市场数据（可选）

		Returns:
			流动性风险指标
		"""
		try:
			if not positions:
				return {}

			metrics = {}

			# 计算组合流动性得分（简化实现）
			liquidity_scores = []
			position_values = []

			for position in positions:
				# 估计流动性（这里使用简化的估计方法）
				# 实际应用中可能需要考虑成交量、买卖价差等因素
				liquidity_score = self._estimate_position_liquidity(position, market_data)
				liquidity_scores.append(liquidity_score)

				market_value = position.get('market_value', 0)
				position_values.append(market_value)

			if position_values:
				total_value = sum(position_values)
				if total_value > 0:
					# 加权平均流动性得分
					weighted_liquidity = np.average(liquidity_scores, weights=position_values)
					metrics['weighted_liquidity_score'] = float(weighted_liquidity)

				# 最不流动资产占比
				min_liquidity_idx = np.argmin(liquidity_scores)
				min_liquidity_weight = position_values[min_liquidity_idx] / total_value
				metrics['illiquid_exposure'] = float(min_liquidity_weight)

			# 估计变现时间
			liquidation_time = self._estimate_liquidation_time(positions, market_data)
			metrics['estimated_liquidation_time'] = float(liquidation_time)

			# 计算流动性风险价值（L-VaR）
			lvar = self._estimate_liquidity_var(positions, market_data)
			metrics['liquidity_var'] = float(lvar)

			return metrics

		except Exception as e:
			raise ValueError(f"流动性风险分析失败: {str(e)}")

	def _calculate_volatility_metrics (
			self,
			returns: pd.Series
	) -> Dict[str, float]:
		"""计算波动率指标"""
		if len(returns) == 0:
			return {'historical_volatility': 0.0, 'realized_volatility': 0.0}

		# 历史波动率（年化）
		historical_vol = returns.std() * np.sqrt(252)

		# 已实现波动率
		realized_vol = np.sqrt(np.sum(returns ** 2) / len(returns) * 252)

		# GARCH波动率预测（简化实现）
		try:
			garch_vol = self._estimate_garch_volatility(returns)
		except Exception as e:
			warnings.warn(f"GARCH波动率估计失败: {str(e)}")
			garch_vol = historical_vol

		return {
			'historical_volatility': float(historical_vol),
			'realized_volatility': float(realized_vol),
			'garch_volatility': float(garch_vol),
			'volatility_ratio': float(realized_vol / historical_vol) if historical_vol > 0 else 0
		}

	def _calculate_var_metrics (
			self,
			returns: pd.Series
	) -> Dict[str, float]:
		"""计算VaR指标"""
		var_results = {'historical': self._calculate_historical_var(returns, self.confidence_level),
		               'parametric': self._calculate_parametric_var(returns, self.confidence_level)}

		# 历史VaR

		# 参数VaR（正态分布假设）

		# Monte Carlo VaR
		try:
			var_results['monte_carlo'] = self._calculate_monte_carlo_var(returns, self.confidence_level)
		except ValueError as e:
			warnings.warn(f"Monte Carlo VaR计算失败: {str(e)}")
			var_results['monte_carlo'] = var_results['historical']

		# 修正VaR（考虑偏度和峰度）
		try:
			var_results['modified'] = self._calculate_modified_var(returns, self.confidence_level)
		except ValueError as e:
			warnings.warn(f"Modified VaR计算失败: {str(e)}")
			var_results['modified'] = var_results['parametric']

		return var_results

	def _calculate_cvar_metrics (
			self,
			returns: pd.Series
	) -> Dict[str, float]:
		"""计算CVaR/ES指标"""
		cvar_results = {'cvar': self._calculate_historical_es(returns, self.confidence_level)}

		# 历史ES

		# 参数ES
		try:
			cvar_results['parametric_es'] = self._calculate_parametric_es(returns, self.confidence_level)
		except ValueError as e:
			warnings.warn(f"Parametric ES计算失败: {str(e)}")
			cvar_results['parametric_es'] = cvar_results['cvar']

		return cvar_results

	def _calculate_max_drawdown_metrics (
			self,
			equity_values: np.ndarray
	) -> Dict[str, float]:
		"""计算最大回撤指标"""
		if len(equity_values) < 2:
			return {'max_drawdown': 0.0, 'avg_drawdown': 0.0, 'drawdown_std': 0.0}

		# 计算所有回撤
		drawdowns = self._calculate_all_drawdowns(equity_values)

		if len(drawdowns) == 0:
			return {'max_drawdown': 0.0, 'avg_drawdown': 0.0, 'drawdown_std': 0.0}

		max_dd = np.max(drawdowns)
		avg_dd = np.mean(drawdowns)
		std_dd = np.std(drawdowns)

		return {
			'max_drawdown': float(max_dd),
			'average_drawdown': float(avg_dd),
			'drawdown_std': float(std_dd),
			'drawdown_count': len(drawdowns)
		}

	def _calculate_other_risk_metrics (
			self,
			returns: pd.Series
	) -> Dict[str, float]:
		"""计算其他风险指标"""
		if len(returns) == 0:
			return {}

		# 偏度风险
		skewness = returns.skew()

		# 峰度风险
		kurtosis = returns.kurtosis()

		# 下半方差
		downside_variance = np.var(returns[returns < returns.mean()]) if len(
			returns[returns < returns.mean()]) > 0 else 0

		# Omega比率
		omega_ratio = self._calculate_omega_ratio(returns)

		# Sortino比率
		sortino_ratio = self._calculate_sortino_ratio(returns)

		# Calmar比率
		# 注意：Calmar比率需要最大回撤数据，这里暂时设为0
		calmar_ratio = 0.0

		return {
			'skewness': float(skewness),
			'kurtosis': float(kurtosis),
			'downside_variance': float(downside_variance),
			'omega_ratio': float(omega_ratio),
			'sortino_ratio': float(sortino_ratio),
			'calmar_ratio': float(calmar_ratio)
		}

	def _calculate_relative_risk_metrics (
			self,
			strategy_returns: pd.Series,
			benchmark_returns: pd.Series
	) -> Dict[str, float]:
		"""计算相对风险指标"""
		# 对齐数据
		common_dates = strategy_returns.index.intersection(benchmark_returns.index)
		if len(common_dates) < 10:
			return {}

		strategy_aligned = strategy_returns.loc[common_dates]
		benchmark_aligned = benchmark_returns.loc[common_dates]

		# 跟踪误差
		excess_returns = strategy_aligned - benchmark_aligned
		tracking_error = excess_returns.std() * np.sqrt(252)

		# Beta系数
		covariance = strategy_aligned.cov(benchmark_aligned)
		benchmark_variance = benchmark_aligned.var()
		beta = covariance / benchmark_variance if benchmark_variance > 0 else 0

		# 残差风险
		residual_risk = np.sqrt(max(0, strategy_aligned.var() - beta ** 2 * benchmark_variance)) * np.sqrt(252)

		return {
			'tracking_error': float(tracking_error),
			'beta': float(beta),
			'residual_risk': float(residual_risk),
			'information_ratio': float(self._calculate_information_ratio(excess_returns))
		}

	@staticmethod
	def _calculate_historical_var (
			returns: pd.Series,
			confidence_level: float
		) -> float:
		"""计算历史VaR"""
		if len(returns) == 0:
			return 0.0

		# 分位数方法
		var = np.percentile(returns, 100 * (1 - confidence_level))
		return float(var)

	@staticmethod
	def _calculate_parametric_var (
			returns: pd.Series,
			confidence_level: float
		) -> float:
		"""计算参数VaR（正态分布假设）"""
		if len(returns) < 2:
			return 0.0

		mean = returns.mean()
		std = returns.std()

		# 正态分布分位数
		z_score = stats.norm.ppf(1 - confidence_level)
		var = mean + z_score * std

		return float(var)

	@staticmethod
	def _calculate_monte_carlo_var (
			returns: pd.Series,
			confidence_level: float,
			n_simulations: int = 10000
		) -> float:
		"""计算Monte Carlo VaR"""
		if len(returns) < 10:
			return 0.0

		# 使用历史数据拟合分布
		from scipy import stats as scipy_stats

		# 拟合正态分布
		mu, sigma = scipy_stats.norm.fit(returns)

		# 生成模拟收益
		np.random.seed(42)
		simulated_returns = np.random.normal(mu, sigma, n_simulations)

		# 计算VaR
		var = np.percentile(simulated_returns, 100 * (1 - confidence_level))
		return float(var)

	@staticmethod
	def _calculate_modified_var (
			returns: pd.Series,
			confidence_level: float
		) -> float:
		"""计算修正VaR（Cornish-Fisher展开）"""
		if len(returns) < 10:
			return 0.0

		# Cornish-Fisher展开
		z = stats.norm.ppf(1 - confidence_level)
		s = returns.skew()
		k = returns.kurtosis()

		# Cornish-Fisher调整后的分位数
		z_cf = z + (z ** 2 - 1) * s / 6 + (z ** 3 - 3 * z) * k / 24 - (2 * z ** 3 - 5 * z) * s ** 2 / 36

		mean = returns.mean()
		std = returns.std()
		var = mean + z_cf * std

		return float(var)

	def _calculate_historical_es (
			self,
			returns: pd.Series,
			confidence_level: float
	) -> float:
		"""计算历史ES/CVaR"""
		if len(returns) == 0:
			return 0.0

		# 计算VaR分位数
		var = self._calculate_historical_var(returns, confidence_level)

		# 计算超过VaR的损失的平均值
		tail_returns = returns[returns <= var]

		if len(tail_returns) == 0:
			return float(var)

		es = tail_returns.mean()
		return float(es)


	@staticmethod
	def _calculate_parametric_es (
			returns: pd.Series,
			confidence_level: float
		) -> float:
		"""计算参数ES（正态分布假设）"""
		if len(returns) < 2:
			return 0.0

		mean = returns.mean()
		std = returns.std()

		# 正态分布的ES公式
		z = stats.norm.ppf(confidence_level)
		es = mean - std * stats.norm.pdf(z) / (1 - confidence_level)

		return float(es)

	@staticmethod
	def _calculate_monte_carlo_es (
			returns: pd.Series,
			confidence_level: float,
			n_simulations: int = 10000
		) -> float:
		"""计算Monte Carlo ES"""
		if len(returns) < 10:
			return 0.0

		# 使用历史数据拟合分布
		from scipy import stats as scipy_stats

		# 拟合正态分布
		mu, sigma = scipy_stats.norm.fit(returns)

		# 生成模拟收益
		np.random.seed(42)
		simulated_returns = np.random.normal(mu, sigma, n_simulations)

		# 计算VaR
		var = np.percentile(simulated_returns, 100 * (1 - confidence_level))

		# 计算ES
		tail_returns = simulated_returns[simulated_returns <= var]

		if len(tail_returns) == 0:
			return float(var)

		es = tail_returns.mean()
		return float(es)

	@staticmethod
	def _calculate_max_drawdown_details (
			equity_values: np.ndarray
		) -> Tuple[float, int, int]:
		"""计算最大回撤详情"""
		if len(equity_values) < 2:
			return 0.0, 0, 0

		# 计算累积最大值
		cumulative_max = np.maximum.accumulate(equity_values)

		# 计算回撤
		drawdowns = (equity_values - cumulative_max) / cumulative_max

		# 找到最大回撤
		max_drawdown = np.min(drawdowns)
		max_drawdown_idx = np.argmin(drawdowns)

		# 找到回撤开始的峰值
		peak_idx = np.argmax(equity_values[:max_drawdown_idx + 1])

		# 计算回撤持续时间
		drawdown_duration = max_drawdown_idx - peak_idx

		# 计算恢复时间
		recovery_idx = None
		for i in range(max_drawdown_idx, len(equity_values)):
			if equity_values[i] >= equity_values[peak_idx]:
				recovery_idx = i
				break

		recovery_time = recovery_idx - max_drawdown_idx if recovery_idx else len(equity_values) - max_drawdown_idx

		return float(max_drawdown), int(drawdown_duration), int(recovery_time)

	def _calculate_drawdown_statistics (
			self,
			equity_values: np.ndarray
	) -> Dict[str, Any]:
		"""计算回撤统计"""
		if len(equity_values) < 2:
			return {'count': 0, 'average': 0.0, 'frequency': 0.0}

		# 计算所有回撤
		drawdowns = self._calculate_all_drawdowns(equity_values)

		if len(drawdowns) == 0:
			return {'count': 0, 'average': 0.0, 'frequency': 0.0}

		# 计算回撤频率（每年代价回撤次数）
		n_years = len(equity_values) / 252  # 假设252个交易日
		frequency = len(drawdowns) / n_years if n_years > 0 else 0

		return {
			'count': len(drawdowns),
			'average': float(np.mean(drawdowns)),
			'std': float(np.std(drawdowns)),
			'median': float(np.median(drawdowns)),
			'frequency': float(frequency)
		}

	@staticmethod
	def _calculate_all_drawdowns (
			equity_values: np.ndarray
		) -> np.ndarray:
		"""计算所有回撤"""
		if len(equity_values) < 2:
			return np.array([])

		# 计算累积最大值
		cumulative_max = np.maximum.accumulate(equity_values)

		# 计算回撤
		drawdowns = (equity_values - cumulative_max) / cumulative_max

		# 识别回撤期（连续负值）
		is_drawdown = drawdowns < 0
		drawdown_periods = []

		i = 0
		while i < len(drawdowns):
			if is_drawdown[i]:
				start = i
				while i < len(drawdowns) and is_drawdown[i]:
					i += 1
				end = i - 1

				# 提取回撤期的值
				period_drawdowns = drawdowns[start:end + 1]
				if len(period_drawdowns) > 0:
					drawdown_periods.append(np.min(period_drawdowns))
			else:
				i += 1

		return np.array(drawdown_periods)

	@staticmethod
	def _calculate_rolling_drawdowns (
			equity_values: np.ndarray,
			window: int = 252
		) -> np.ndarray:
		"""计算滚动最大回撤"""
		if len(equity_values) < window:
			return np.array([])

		rolling_drawdowns = []

		for i in range(window, len(equity_values) + 1):
			window_data = equity_values[i - window:i]
			if len(window_data) > 0:
				max_val = float(np.max(window_data))
				min_val = float(np.min(window_data))
				drawdown = float((min_val - max_val) / max_val) if max_val > 0.0 else 0.0
				rolling_drawdowns.append(drawdown)

		return np.array(rolling_drawdowns)

	@staticmethod
	def _identify_major_drawdowns (
			equity_values: np.ndarray,
			threshold: float = -0.10  # 超过10%的回撤
		) -> List[Dict[str, Any]]:
		"""识别主要回撤期"""
		if len(equity_values) < 2:
			return []

		# 计算累积最大值和回撤
		cumulative_max = np.maximum.accumulate(equity_values)
		drawdowns = (equity_values - cumulative_max) / cumulative_max

		# 识别回撤期
		is_drawdown = drawdowns < threshold
		major_drawdowns = []

		i = 0
		while i < len(drawdowns):
			if is_drawdown[i]:
				start = i
				while i < len(drawdowns) and is_drawdown[i]:
					i += 1
				end = i - 1

				# 提取回撤期的详细信息
				period_drawdowns = drawdowns[start:end + 1]
				max_dd_in_period = np.min(period_drawdowns)
				duration = end - start + 1

				major_drawdowns.append({
					'start_index': start,
					'end_index': end,
					'max_drawdown': float(max_dd_in_period),
					'duration': duration
				})
			else:
				i += 1

		return major_drawdowns

	def _perform_stress_tests (
			self,
			returns: pd.Series
	) -> Dict[str, Decimal]:
		"""执行压力测试"""
		stress_results = {}

		# 定义压力场景
		stress_scenarios = {
			'market_crash': -0.05,
			'flash_crash': -0.09,
			'volatility_spike': returns.std() * 3,
			'interest_rate_shock': -0.02
		}

		for scenario, shock in stress_scenarios.items():
			# 应用压力冲击
			stressed_returns = returns + shock

			# 计算压力下的VaR
			stressed_var = self._calculate_historical_var(stressed_returns, self.confidence_level)

			stress_results[scenario] = Decimal(str(stressed_var))

		return stress_results


	@staticmethod
	def _estimate_liquidity_metrics (
			positions: Optional[List[Dict[str, Any]]]
		) -> Dict[str, Decimal]:
		"""估计流动性指标"""
		if not positions:
			return {}

		# 简化实现
		return {
			'estimated_bid_ask_spread': Decimal('0.001'),  # 估计买卖价差
			'estimated_market_impact': Decimal('0.0005'),  # 估计市场冲击成本
			'liquidity_score': Decimal('0.8')  # 流动性得分（0-1）
		}

	@staticmethod
	def _calculate_correlation_matrix (
			positions: Optional[List[Dict[str, Any]]]
		) -> Dict[str, Dict[str, Decimal]]:
		"""计算相关性矩阵"""
		if not positions or len(positions) < 2:
			return {}

		# 简化实现：返回单位矩阵
		correlation_matrix = {}

		for i, pos1 in enumerate(positions):
			code1 = pos1.get('ts_code', f'asset_{i}')
			correlation_matrix[code1] = {}

			for j, pos2 in enumerate(positions):
				code2 = pos2.get('ts_code', f'asset_{j}')
				if i == j:
					correlation_matrix[code1][code2] = Decimal('1.0')
				else:
					correlation_matrix[code1][code2] = Decimal('0.3')  # 简化假设

		return correlation_matrix

	@staticmethod
	def _calculate_risk_contributions (
			positions: Optional[List[Dict[str, Any]]]
		) -> Dict[str, Decimal]:
		"""计算风险贡献度"""
		if not positions:
			return {}

		# 简化实现：按市值比例分配风险
		total_value = sum(pos.get('market_value', 0) for pos in positions)

		if total_value == 0:
			return {}

		risk_contributions = {}

		for position in positions:
			code = position.get('ts_code', 'unknown')
			weight = position.get('market_value', 0) / total_value
			risk_contributions[code] = Decimal(str(weight))

		return risk_contributions

	@staticmethod
	def _estimate_garch_volatility (
			returns: pd.Series,
			p: int = 1,
			q: int = 1
		) -> float:
		"""估计GARCH波动率"""
		if len(returns) < 50:
			return returns.std() * np.sqrt(252)

		try:
			import arch

			# 拟合GARCH(1,1)模型
			model = arch.arch_model(returns * 100, vol='GARCH', p=p, q=q)
			result = model.fit(disp='off')

			# 预测下一期波动率
			forecast = result.forecast(horizon=1)
			pred_vol = np.sqrt(forecast.variance.values[-1, 0]) / 100  # 转换回原始尺度

			return float(pred_vol * np.sqrt(252))

		except Exception as e:
			warnings.warn(f"GARCH模型拟合失败: {str(e)}，使用历史波动率")
			return returns.std() * np.sqrt(252)

	@staticmethod
	def _calculate_omega_ratio (
			returns: pd.Series,
			threshold: float = 0.0
		) -> float:
		"""计算Omega比率"""
		if len(returns) == 0:
			return 0.0

		# 计算高于阈值的收益和低于阈值的损失
		gains = returns[returns > threshold] - threshold
		losses = threshold - returns[returns < threshold]

		if len(losses) == 0:
			return float('inf')

		omega = gains.sum() / losses.sum() if losses.sum() > 0 else float('inf')
		return float(omega)

	@staticmethod
	def _calculate_downside_risk (
			returns: pd.Series,
			mar: float = 0.0
		) -> float:
		"""计算下行风险"""
		if len(returns) == 0:
			return 0.0

		# 计算低于门槛收益率的偏差
		downside_deviations = returns[returns < mar] - mar
		if len(downside_deviations) == 0:
			return 0.0

		downside_risk = np.sqrt(np.mean(downside_deviations ** 2))
		return float(downside_risk)

	def _calculate_sortino_ratio (
			self,
			returns: pd.Series,
			mar: float = 0.0
	) -> float:
		"""计算Sortino比率"""
		if len(returns) == 0:
			return 0.0

		mean_return = returns.mean()
		downside_risk = self._calculate_downside_risk(returns, mar)

		if downside_risk == 0:
			return 0.0

		sortino = (mean_return - mar) / downside_risk * np.sqrt(252)
		return float(sortino)

	@staticmethod
	def _calculate_information_ratio (
			excess_returns: pd.Series
		) -> float:
		"""计算信息比率"""
		if len(excess_returns) == 0:
			return 0.0

		mean_excess = excess_returns.mean()
		std_excess = excess_returns.std()

		if std_excess == 0:
			return 0.0

		info_ratio = mean_excess / std_excess * np.sqrt(252)
		return float(info_ratio)

	@staticmethod
	def _calculate_gini_coefficient (
			weights: np.ndarray
		) -> float:
		"""计算基尼系数"""
		if len(weights) == 0:
			return 0.0

		# 按大小排序
		sorted_weights = np.sort(weights)

		# 计算累积分布
		n = len(sorted_weights)
		index = np.arange(1, n + 1)

		# 计算基尼系数
		gini = (np.sum((2 * index - n - 1) * sorted_weights)) / (n * np.sum(sorted_weights))

		return float(gini)

	@staticmethod
	def _calculate_entropy_index (
			weights: np.ndarray
		) -> float:
		"""计算熵指数"""
		if len(weights) == 0:
			return 0.0

		# 移除零权重
		non_zero_weights = weights[weights > 0]

		if len(non_zero_weights) == 0:
			return 0.0

		# 计算香农熵
		entropy = float(np.sum(non_zero_weights * np.log(non_zero_weights)))

		# 归一化到[0, 1]
		max_entropy = float(np.log(len(non_zero_weights)))
		if max_entropy > 0.0:
			entropy_index = float(entropy / max_entropy)
		else:
			entropy_index = 0.0

		return float(entropy_index)

	@staticmethod
	def _calculate_sector_concentration (
			positions: List[Dict[str, Any]]
		) -> Dict[str, float]:
		"""计算行业集中度"""
		if not positions:
			return {}

		# 按行业分组
		sector_values = {}

		for position in positions:
			sector = position.get('sector', 'unknown')
			market_value = position.get('market_value', 0)

			if sector not in sector_values:
				sector_values[sector] = 0

			sector_values[sector] += market_value

		# 计算总市值
		total_value = sum(sector_values.values())

		if total_value == 0:
			return {}

		# 计算行业权重
		sector_weights = {sector: value / total_value for sector, value in sector_values.items()}

		# 计算行业HHI
		sector_hhi = sum(weight ** 2 for weight in sector_weights.values())

		# 最大行业权重
		max_sector_weight = max(sector_weights.values()) if sector_weights else 0

		return {
			'sector_hhi': float(sector_hhi),
			'max_sector_weight': float(max_sector_weight),
			'sector_weights': sector_weights
		}

	@staticmethod
	def _estimate_position_liquidity (
			position: Dict[str, Any],
			market_data: Optional[Dict[str, Any]] = None
		) -> float:
		"""估计头寸流动性"""
		_ = market_data
		market_value = position.get('market_value', 0)

		if market_value <= 0:
			return 0.0

		if market_value < 1e6:
			return 0.9
		elif market_value < 1e7:
			return 0.7
		elif market_value < 1e8:
			return 0.5
		else:
			return 0.3

	@staticmethod
	def _estimate_liquidation_time (
			positions: List[Dict[str, Any]],
			market_data: Optional[Dict[str, Any]] = None
		) -> float:
		"""估计变现时间（天数）"""
		_ = market_data
		if not positions:
			return 0.0

		total_value = sum(pos.get('market_value', 0) for pos in positions)

		if total_value <= 0:
			return 0.0

		if total_value < 1e6:
			return 1.0
		elif total_value < 1e7:
			return 3.0
		elif total_value < 1e8:
			return 7.0
		else:
			return 15.0

	@staticmethod
	def _estimate_liquidity_var (
			positions: List[Dict[str, Any]],
			market_data: Optional[Dict[str, Any]] = None
		) -> float:
		"""估计流动性风险价值"""
		_ = market_data
		if not positions:
			return 0.0

		total_value = sum(pos.get('market_value', 0) for pos in positions)
		lvar = total_value * 0.01

		return float(lvar)