# -*- coding: utf-8 -*-
"""
统计分析工具模块
提供统计分析相关工具函数，包括统计指标计算、假设检验、回归分析等
位置：quant_server/modules/events/utils/statistic_utils.py
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple, Union
from scipy import stats
import warnings
from datetime import datetime, timedelta
from decimal import Decimal


class StatisticUtils:
	"""统计分析工具类"""

	@staticmethod
	def calculate_returns (prices: Union[List[float], pd.Series],
	                       period: str = 'daily') -> np.ndarray:
		"""
		计算收益率序列

		Args:
			prices: 价格序列
			period: 收益率周期 ('daily', 'weekly', 'monthly')

		Returns:
			np.ndarray: 收益率序列
		"""
		if isinstance(prices, pd.Series):
			prices = prices.values

		prices = np.array(prices)
		if len(prices) < 2:
			return np.array([])

		returns = np.diff(prices) / prices[:-1]

		# 根据周期调整年化因子
		period_factors = {'daily': 252, 'weekly': 52, 'monthly': 12}
		if period in period_factors:
			returns = returns * np.sqrt(period_factors[period])

		return returns

	@staticmethod
	def calculate_sharpe_ratio (returns: Union[List[float], pd.Series],
	                            risk_free_rate: float = 0.03,
	                            period: str = 'daily') -> float:
		"""
		计算夏普比率

		Args:
			returns: 收益率序列
			risk_free_rate: 无风险利率（年化）
			period: 收益率周期

		Returns:
			float: 夏普比率
		"""
		if len(returns) < 2:
			return 0.0

		returns = np.array(returns)
		excess_returns = returns - risk_free_rate / 252  # 转换为日无风险利率

		if np.std(excess_returns) == 0:
			return 0.0

		sharpe = np.mean(excess_returns) / np.std(excess_returns)

		# 年化调整
		period_factors = {'daily': np.sqrt(252), 'weekly': np.sqrt(52), 'monthly': np.sqrt(12)}
		if period in period_factors:
			sharpe *= period_factors[period]

		return float(sharpe)

	@staticmethod
	def calculate_sortino_ratio (returns: Union[List[float], pd.Series],
	                             risk_free_rate: float = 0.03,
	                             period: str = 'daily') -> float:
		"""
		计算索提诺比率（只考虑下行风险）

		Args:
			returns: 收益率序列
			risk_free_rate: 无风险利率
			period: 收益率周期

		Returns:
			float: 索提诺比率
		"""
		if len(returns) < 2:
			return 0.0

		returns = np.array(returns)
		excess_returns = returns - risk_free_rate / 252

		# 只计算负的收益
		downside_returns = excess_returns[excess_returns < 0]

		if len(downside_returns) == 0 or np.std(downside_returns) == 0:
			return 0.0

		sortino = np.mean(excess_returns) / np.std(downside_returns)

		# 年化调整
		period_factors = {'daily': np.sqrt(252), 'weekly': np.sqrt(52), 'monthly': np.sqrt(12)}
		if period in period_factors:
			sortino *= period_factors[period]

		return float(sortino)

	@staticmethod
	def calculate_max_drawdown (cumulative_returns: Union[List[float], pd.Series]) -> Tuple[float, int, int]:
		"""
		计算最大回撤

		Args:
			cumulative_returns: 累计收益率序列

		Returns:
			Tuple[float, int, int]: (最大回撤比例, 回撤开始位置, 回撤结束位置)
		"""
		if len(cumulative_returns) < 2:
			return 0.0, 0, 0

		cumulative_returns = np.array(cumulative_returns)
		peak = cumulative_returns[0]
		max_drawdown = 0.0
		peak_index = 0
		trough_index = 0

		for i in range(1, len(cumulative_returns)):
			if cumulative_returns[i] > peak:
				peak = cumulative_returns[i]
				peak_index = i
			else:
				drawdown = (peak - cumulative_returns[i]) / peak if peak != 0 else 0
				if drawdown > max_drawdown:
					max_drawdown = drawdown
					trough_index = i

		return float(max_drawdown), peak_index, trough_index

	@staticmethod
	def calculate_calmar_ratio (returns: Union[List[float], pd.Series],
	                            max_drawdown: float,
	                            period: str = 'daily') -> float:
		"""
		计算卡玛比率（年化收益率/最大回撤）

		Args:
			returns: 收益率序列
			max_drawdown: 最大回撤
			period: 收益率周期

		Returns:
			float: 卡玛比率
		"""
		if len(returns) < 2 or max_drawdown == 0:
			return 0.0

		returns = np.array(returns)
		annual_return = np.mean(returns) * 252  # 简单年化

		return float(annual_return / max_drawdown)

	@staticmethod
	def calculate_information_ratio (portfolio_returns: Union[List[float], pd.Series],
	                                 benchmark_returns: Union[List[float], pd.Series]) -> float:
		"""
		计算信息比率

		Args:
			portfolio_returns: 组合收益率
			benchmark_returns: 基准收益率

		Returns:
			float: 信息比率
		"""
		if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
			return 0.0

		portfolio_returns = np.array(portfolio_returns)
		benchmark_returns = np.array(benchmark_returns)

		active_returns = portfolio_returns - benchmark_returns
		tracking_error = np.std(active_returns)

		if tracking_error == 0:
			return 0.0

		information_ratio = np.mean(active_returns) / tracking_error * np.sqrt(252)
		return float(information_ratio)

	@staticmethod
	def calculate_beta_alpha (portfolio_returns: Union[List[float], pd.Series],
	                          benchmark_returns: Union[List[float], pd.Series],
	                          risk_free_rate: float = 0.03) -> Tuple[float, float]:
		"""
		计算Beta和Alpha

		Args:
			portfolio_returns: 组合收益率
			benchmark_returns: 基准收益率
			risk_free_rate: 无风险利率

		Returns:
			Tuple[float, float]: (Beta系数, Alpha值)
		"""
		if len(portfolio_returns) != len(benchmark_returns) or len(portfolio_returns) < 2:
			return 0.0, 0.0

		portfolio_returns = np.array(portfolio_returns)
		benchmark_returns = np.array(benchmark_returns)

		# 计算协方差和方差
		covariance = np.cov(portfolio_returns, benchmark_returns)[0, 1]
		variance = np.var(benchmark_returns)

		if variance == 0:
			return 0.0, 0.0

		beta = covariance / variance

		# 计算Alpha（年化）
		portfolio_mean = np.mean(portfolio_returns) * 252
		benchmark_mean = np.mean(benchmark_returns) * 252
		alpha = portfolio_mean - risk_free_rate - beta * (benchmark_mean - risk_free_rate)

		return float(beta), float(alpha)

	@staticmethod
	def calculate_skewness_kurtosis (returns: Union[List[float], pd.Series]) -> Tuple[float, float]:
		"""
		计算偏度和峰度

		Args:
			returns: 收益率序列

		Returns:
			Tuple[float, float]: (偏度, 峰度)
		"""
		if len(returns) < 3:
			return 0.0, 0.0

		returns = np.array(returns)
		skewness = stats.skew(returns)
		kurtosis = stats.kurtosis(returns)

		return float(skewness), float(kurtosis)

	@staticmethod
	def calculate_var_cvar (returns: Union[List[float], pd.Series],
	                        confidence_level: float = 0.95) -> Tuple[float, float]:
		"""
		计算VaR（在险价值）和CVaR（条件在险价值）

		Args:
			returns: 收益率序列
			confidence_level: 置信水平

		Returns:
			Tuple[float, float]: (VaR值, CVaR值)
		"""
		if len(returns) < 10:
			return 0.0, 0.0

		returns = np.array(returns)

		# 历史模拟法计算VaR
		sorted_returns = np.sort(returns)
		index = int((1 - confidence_level) * len(sorted_returns))
		var = -sorted_returns[index]

		# 计算CVaR（超过VaR部分的平均损失）
		tail_returns = sorted_returns[:index]
		cvar = -np.mean(tail_returns) if len(tail_returns) > 0 else var

		return float(var), float(cvar)

	@staticmethod
	def calculate_t_statistic (sample_mean: float,
	                           population_mean: float,
	                           sample_std: float,
	                           sample_size: int) -> float:
		"""
		计算t统计量

		Args:
			sample_mean: 样本均值
			population_mean: 总体均值
			sample_std: 样本标准差
			sample_size: 样本大小

		Returns:
			float: t统计量
		"""
		if sample_size <= 1 or sample_std == 0:
			return 0.0

		standard_error = sample_std / np.sqrt(sample_size)
		t_stat = (sample_mean - population_mean) / standard_error

		return float(t_stat)

	@staticmethod
	def calculate_correlation_matrix (data: pd.DataFrame) -> pd.DataFrame:
		"""
		计算相关性矩阵

		Args:
			data: 数据DataFrame，每列代表一个资产

		Returns:
			pd.DataFrame: 相关性矩阵
		"""
		return data.corr()

	@staticmethod
	def perform_hypothesis_test (sample_data: List[float],
	                             test_type: str = 't-test',
	                             mu: float = 0,
	                             alternative: str = 'two-sided') -> Dict[str, Any]:
		"""
		执行假设检验

		Args:
			sample_data: 样本数据
			test_type: 检验类型 ('t-test', 'normality-test')
			mu: 假设的均值
			alternative: 备择假设 ('two-sided', 'greater', 'less')

		Returns:
			Dict[str, Any]: 检验结果
		"""
		if len(sample_data) < 2:
			return {'statistic': 0, 'p_value': 1, 'reject_null': False}

		sample_data = np.array(sample_data)

		if test_type == 't-test':
			t_stat, p_value = stats.ttest_1samp(sample_data, mu)

			# 根据备择假设调整p值
			if alternative == 'greater':
				p_value = 1 - p_value / 2 if t_stat > 0 else p_value / 2
			elif alternative == 'less':
				p_value = 1 - p_value / 2 if t_stat < 0 else p_value / 2

			reject_null = p_value < 0.05

			return {
				'test_type': 'one_sample_t_test',
				'statistic': float(t_stat),
				'p_value': float(p_value),
				'reject_null': reject_null,
				'alternative': alternative
			}

		elif test_type == 'normality-test':
			# Shapiro-Wilk正态性检验
			if len(sample_data) > 5000:
				# 对于大样本，使用部分数据
				sample_data = np.random.choice(sample_data, 5000, replace=False)

			stat, p_value = stats.shapiro(sample_data)

			return {
				'test_type': 'shapiro_wilk_test',
				'statistic': float(stat),
				'p_value': float(p_value),
				'reject_null': p_value < 0.05,
				'is_normal': p_value >= 0.05
			}

		else:
			raise ValueError(f"不支持的检验类型: {test_type}")

	@staticmethod
	def calculate_rolling_statistics (data: pd.Series,
	                                  window: int = 20,
	                                  statistic: str = 'mean') -> pd.Series:
		"""
		计算滚动统计量

		Args:
			data: 数据序列
			window: 滚动窗口大小
			statistic: 统计量类型 ('mean', 'std', 'min', 'max', 'skew', 'kurt')

		Returns:
			pd.Series: 滚动统计量序列
		"""
		if statistic == 'mean':
			return data.rolling(window=window).mean()
		elif statistic == 'std':
			return data.rolling(window=window).std()
		elif statistic == 'min':
			return data.rolling(window=window).min()
		elif statistic == 'max':
			return data.rolling(window=window).max()
		elif statistic == 'skew':
			return data.rolling(window=window).skew()
		elif statistic == 'kurt':
			return data.rolling(window=window).kurt()
		else:
			raise ValueError(f"不支持的统计量类型: {statistic}")

	@staticmethod
	def calculate_compound_annual_growth_rate (initial_value: float,
	                                           final_value: float,
	                                           years: float) -> float:
		"""
		计算复合年增长率 (CAGR)

		Args:
			initial_value: 初始值
			final_value: 最终值
			years: 年数

		Returns:
			float: 复合年增长率
		"""
		if initial_value <= 0 or years <= 0:
			return 0.0

		cagr = (final_value / initial_value) ** (1 / years) - 1
		return float(cagr)

	@staticmethod
	def calculate_win_rate (trades: List[Dict[str, Any]]) -> float:
		"""
		计算胜率

		Args:
			trades: 交易记录列表，每个交易包含 'profit' 字段

		Returns:
			float: 胜率（0-1之间）
		"""
		if not trades:
			return 0.0

		winning_trades = [trade for trade in trades if trade.get('profit', 0) > 0]
		win_rate = len(winning_trades) / len(trades)

		return float(win_rate)

	@staticmethod
	def calculate_profit_factor (trades: List[Dict[str, Any]]) -> float:
		"""
		计算盈利因子

		Args:
			trades: 交易记录列表

		Returns:
			float: 盈利因子
		"""
		if not trades:
			return 0.0

		gross_profit = sum(trade.get('profit', 0) for trade in trades if trade.get('profit', 0) > 0)
		gross_loss = abs(sum(trade.get('profit', 0) for trade in trades if trade.get('profit', 0) < 0))

		if gross_loss == 0:
			return float('inf') if gross_profit > 0 else 0.0

		return float(gross_profit / gross_loss)

	@staticmethod
	def calculate_average_win_loss (trades: List[Dict[str, Any]]) -> Tuple[float, float]:
		"""
		计算平均盈利和平均亏损

		Args:
			trades: 交易记录列表

		Returns:
			Tuple[float, float]: (平均盈利, 平均亏损)
		"""
		winning_trades = [trade for trade in trades if trade.get('profit', 0) > 0]
		losing_trades = [trade for trade in trades if trade.get('profit', 0) < 0]

		avg_win = np.mean([t['profit'] for t in winning_trades]) if winning_trades else 0.0
		avg_loss = np.mean([abs(t['profit']) for t in losing_trades]) if losing_trades else 0.0

		return float(avg_win), float(avg_loss)