"""
金融计算器模块
提供金融相关的计算功能
"""

import numpy as np
import pandas as pd
from typing import Union, List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta


class ReturnType(Enum):
	"""收益率类型枚举"""
	SIMPLE = "simple"
	LOG = "log"
	TOTAL = "total"


class Frequency(Enum):
	"""频率枚举"""
	DAILY = "daily"
	WEEKLY = "weekly"
	MONTHLY = "monthly"
	QUARTERLY = "quarterly"
	YEARLY = "yearly"


@dataclass
class FinancialMetrics:
	"""金融指标计算结果"""
	returns: np.ndarray
	cumulative_returns: np.ndarray
	annualized_return: float
	annualized_volatility: float
	sharpe_ratio: float
	sortino_ratio: float
	max_drawdown: float
	max_drawdown_duration: int
	calmar_ratio: float
	var_95: float
	cvar_95: float
	omega_ratio: float
	information_ratio: Optional[float] = None
	alpha: Optional[float] = None
	beta: Optional[float] = None
	tracking_error: Optional[float] = None
	treynor_ratio: Optional[float] = None
	jensen_alpha: Optional[float] = None


class FinancialCalculator:
	"""
	金融计算器类
	提供金融相关的计算功能
	"""

	# 交易天数常量（用于年化计算）
	TRADING_DAYS = {
		Frequency.DAILY: 252,
		Frequency.WEEKLY: 52,
		Frequency.MONTHLY: 12,
		Frequency.QUARTERLY: 4,
		Frequency.YEARLY: 1
	}

	def __init__ (self, risk_free_rate: float = 0.03,
	              frequency: Frequency = Frequency.DAILY):
		"""
		初始化金融计算器

		Args:
			risk_free_rate: 无风险利率
			frequency: 数据频率
		"""
		self.risk_free_rate = risk_free_rate
		self.frequency = frequency
		self.trading_days = self.TRADING_DAYS[frequency]

	def calculate_returns (self, prices: Union[List[float], np.ndarray, pd.Series],
	                       return_type: ReturnType = ReturnType.SIMPLE) -> np.ndarray:
		"""
		计算收益率

		Args:
			prices: 价格序列
			return_type: 收益率类型

		Returns:
			np.ndarray: 收益率序列
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) < 2:
			raise ValueError("价格序列长度必须至少为2")

		if return_type == ReturnType.SIMPLE:
			returns = prices[1:] / prices[:-1] - 1
			# 添加第一个NaN值以保持长度一致
			returns = np.insert(returns, 0, np.nan)

		elif return_type == ReturnType.LOG:
			ratios = prices[1:] / prices[:-1]
			ratios = np.where(ratios > 0, ratios, np.nan)  # v2.4: 屏蔽 ≤0 的无效比值
			returns = np.log(ratios)
			returns = np.where(np.isfinite(returns), returns, 0.0)  # v2.4: 屏蔽 inf
			returns = np.insert(returns, 0, np.nan)

		elif return_type == ReturnType.TOTAL:
			returns = (prices[1:] - prices[:-1]) / prices[:-1]
			returns = np.insert(returns, 0, np.nan)

		else:
			raise ValueError(f"不支持的收益率类型: {return_type}")

		return returns

	def log_returns (self, prices: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
		"""
		计算对数收益率

		Args:
			prices: 价格序列

		Returns:
			np.ndarray: 对数收益率序列
		"""
		return self.calculate_returns(prices, ReturnType.LOG)

	def cumulative_returns (self, returns: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
		"""
		计算累计收益率

		Args:
			returns: 收益率序列

		Returns:
			np.ndarray: 累计收益率序列
		"""
		if isinstance(returns, (list, pd.Series)):
			returns = np.array(returns)

		# 过滤掉NaN值
		valid_returns = returns[~np.isnan(returns)]

		if len(valid_returns) == 0:
			return np.array([0.0])

		cumulative = np.cumprod(1 + valid_returns) - 1
		return cumulative

	def annualized_return (self, returns: Union[List[float], np.ndarray, pd.Series]) -> float:
		"""
		计算年化收益率

		Args:
			returns: 收益率序列

		Returns:
			float: 年化收益率
		"""
		if isinstance(returns, (list, pd.Series)):
			returns = np.array(returns)

		# 过滤掉NaN值
		valid_returns = returns[~np.isnan(returns)]

		if len(valid_returns) == 0:
			return 0.0

		# 计算总收益率
		total_return = np.prod(1 + valid_returns) - 1

		# 年化
		n_periods = len(valid_returns)
		if n_periods == 0:
			return 0.0

		# 计算年化因子
		annual_factor = self.trading_days / n_periods

		# 年化收益率
		annualized_ret = (1 + total_return) ** annual_factor - 1

		return annualized_ret

	def annualized_volatility (self, returns: Union[List[float], np.ndarray, pd.Series]) -> float:
		"""
		计算年化波动率

		Args:
			returns: 收益率序列

		Returns:
			float: 年化波动率
		"""
		if isinstance(returns, (list, pd.Series)):
			returns = np.array(returns)

		# 过滤掉NaN值
		valid_returns = returns[~np.isnan(returns)]

		if len(valid_returns) < 2:
			return 0.0

		# 计算日波动率
		daily_vol = np.std(valid_returns, ddof=1)

		# 年化
		annual_vol = daily_vol * np.sqrt(self.trading_days)

		return annual_vol

	def sharpe_ratio (self, returns: Union[List[float], np.ndarray, pd.Series],
	                  risk_free_rate: Optional[float] = None) -> float:
		"""
		计算夏普比率

		Args:
			returns: 收益率序列
			risk_free_rate: 无风险利率，如为None则使用初始化时的值

		Returns:
			float: 夏普比率
		"""
		if risk_free_rate is None:
			risk_free_rate = self.risk_free_rate

		if isinstance(returns, (list, pd.Series)):
			returns = np.array(returns)
		valid_returns = returns[~np.isnan(returns)]
		if len(valid_returns) < 2:
			return 0.0

		# 修复 2026-08（C4）：日频超额口径 + ddof=1——
		# 旧实现为 (年化收益 - 日化rf)/年化波动，维度错误；
		# 统一 GIPS 口径：mean(r - rf/252) / std(ddof=1) × √252
		rf_daily = risk_free_rate / self.trading_days
		excess = valid_returns - rf_daily
		std = float(np.std(excess, ddof=1))
		if std == 0:
			return 0.0

		return float(np.mean(excess) / std * np.sqrt(self.trading_days))

	def sortino_ratio (self, returns: Union[List[float], np.ndarray, pd.Series],
	                   risk_free_rate: Optional[float] = None,
	                   target_return: float = 0) -> float:
		"""
		计算索提诺比率

		Args:
			returns: 收益率序列
			risk_free_rate: 无风险利率
			target_return: 目标收益率

		Returns:
			float: 索提诺比率
		"""
		if risk_free_rate is None:
			risk_free_rate = self.risk_free_rate

		annual_return = self.annualized_return(returns)

		if isinstance(returns, (list, pd.Series)):
			returns = np.array(returns)

		# 过滤掉NaN值
		valid_returns = returns[~np.isnan(returns)]

		# 计算下行波动率
		downside_returns = valid_returns[valid_returns < target_return]

		if len(downside_returns) == 0:
			downside_vol = 0.0
		else:
			downside_vol = np.std(downside_returns, ddof=1) * np.sqrt(self.trading_days)

		if downside_vol == 0:
			return 0.0

		# 将年化无风险利率转换为与收益率相同的频率
		risk_free_rate_period = (1 + risk_free_rate) ** (1 / self.trading_days) - 1
		excess_return = annual_return - risk_free_rate_period

		return excess_return / downside_vol

	def maximum_drawdown (self, prices: Union[List[float], np.ndarray, pd.Series]) -> float:
		"""
		计算最大回撤

		Args:
			prices: 价格序列

		Returns:
			float: 最大回撤
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) == 0:
			return 0.0

		# 计算累计最大值
		cumulative_max = np.maximum.accumulate(prices)

		# 计算回撤
		drawdowns = (prices - cumulative_max) / cumulative_max

		# 最大回撤（负数表示下跌）
		max_drawdown = np.min(drawdowns)

		return max_drawdown

	def drawdown_duration (self, prices: Union[List[float], np.ndarray, pd.Series]) -> int:
		"""
		计算最大回撤持续时间（周期数）

		Args:
			prices: 价格序列

		Returns:
			int: 最大回撤持续时间
		"""
		if isinstance(prices, (list, pd.Series)):
			prices = np.array(prices)

		if len(prices) == 0:
			return 0

		# 计算累计最大值
		cumulative_max = np.maximum.accumulate(prices)

		# 计算是否处于回撤中
		in_drawdown = prices < cumulative_max

		# 找到最长的连续回撤期
		max_duration = 0
		current_duration = 0

		for is_drawdown in in_drawdown:
			if is_drawdown:
				current_duration += 1
				max_duration = max(max_duration, current_duration)
			else:
				current_duration = 0

		return max_duration

	def calmar_ratio (self, prices: Union[List[float], np.ndarray, pd.Series],
	                  risk_free_rate: Optional[float] = None) -> float:
		"""
		计算Calmar比率

		Args:
			prices: 价格序列
			risk_free_rate: 无风险利率

		Returns:
			float: Calmar比率
		"""
		if risk_free_rate is None:
			risk_free_rate = self.risk_free_rate

		# 计算收益率
		returns = self.calculate_returns(prices)

		# 年化收益率
		annual_return = self.annualized_return(returns)

		# 最大回撤
		max_dd = self.maximum_drawdown(prices)

		if max_dd == 0:
			return 0.0

		# 将年化无风险利率转换为与收益率相同的频率
		risk_free_rate_period = (1 + risk_free_rate) ** (1 / self.trading_days) - 1
		excess_return = annual_return - risk_free_rate_period

		return excess_return / abs(max_dd)

	def value_at_risk (self, returns: Union[List[float], np.ndarray, pd.Series],
	                   confidence: float = 0.95) -> float:
		"""
		计算在险价值 (VaR)

		Args:
			returns: 收益率序列
			confidence: 置信水平

		Returns:
			float: 在险价值
		"""
		if isinstance(returns, (list, pd.Series)):
			returns = np.array(returns)

		# 过滤掉NaN值
		valid_returns = returns[~np.isnan(returns)]

		if len(valid_returns) == 0:
			return 0.0

		# 计算分位数
		var = np.percentile(valid_returns, (1 - confidence) * 100)

		return var

	def conditional_value_at_risk (self, returns: Union[List[float], np.ndarray, pd.Series],
	                               confidence: float = 0.95) -> float:
		"""
		计算条件在险价值 (CVaR)

		Args:
			returns: 收益率序列
			confidence: 置信水平

		Returns:
			float: 条件在险价值
		"""
		if isinstance(returns, (list, pd.Series)):
			returns = np.array(returns)

		# 过滤掉NaN值
		valid_returns = returns[~np.isnan(returns)]

		if len(valid_returns) == 0:
			return 0.0

		# 计算VaR
		var = self.value_at_risk(valid_returns, confidence)

		# 计算超过VaR的收益率的均值
		losses_beyond_var = valid_returns[valid_returns <= var]

		if len(losses_beyond_var) == 0:
			return var

		cvar = np.mean(losses_beyond_var)

		return cvar

	def omega_ratio (self, returns: Union[List[float], np.ndarray, pd.Series],
	                 threshold: float = 0) -> float:
		"""
		计算Omega比率

		Args:
			returns: 收益率序列
			threshold: 阈值

		Returns:
			float: Omega比率
		"""
		if isinstance(returns, (list, pd.Series)):
			returns = np.array(returns)

		# 过滤掉NaN值
		valid_returns = returns[~np.isnan(returns)]

		if len(valid_returns) == 0:
			return 1.0

		# 计算超过阈值的收益
		gains = valid_returns[valid_returns > threshold]
		losses = valid_returns[valid_returns <= threshold]

		if len(losses) == 0:
			return float('inf')

		# 计算Omega比率
		gains_sum = np.sum(gains - threshold)
		losses_sum = np.sum(threshold - losses)

		if losses_sum == 0:
			return float('inf')

		omega = gains_sum / losses_sum

		return omega

	def information_ratio (self, portfolio_returns: Union[List[float], np.ndarray, pd.Series],
	                       benchmark_returns: Union[List[float], np.ndarray, pd.Series]) -> float:
		"""
		计算信息比率

		Args:
			portfolio_returns: 组合收益率序列
			benchmark_returns: 基准收益率序列

		Returns:
			float: 信息比率
		"""
		if isinstance(portfolio_returns, (list, pd.Series)):
			portfolio_returns = np.array(portfolio_returns)
		if isinstance(benchmark_returns, (list, pd.Series)):
			benchmark_returns = np.array(benchmark_returns)

		# 计算超额收益
		excess_returns = portfolio_returns - benchmark_returns

		# 过滤掉NaN值
		valid_excess = excess_returns[~np.isnan(excess_returns)]

		if len(valid_excess) < 2:
			return 0.0

		# 计算信息比率
		mean_excess = np.mean(valid_excess)
		std_excess = np.std(valid_excess, ddof=1)

		if std_excess == 0:
			return 0.0

		# 年化
		ir = mean_excess / std_excess * np.sqrt(self.trading_days)

		return ir

	def tracking_error (self, portfolio_returns: Union[List[float], np.ndarray, pd.Series],
	                    benchmark_returns: Union[List[float], np.ndarray, pd.Series]) -> float:
		"""
		计算跟踪误差

		Args:
			portfolio_returns: 组合收益率序列
			benchmark_returns: 基准收益率序列

		Returns:
			float: 跟踪误差
		"""
		if isinstance(portfolio_returns, (list, pd.Series)):
			portfolio_returns = np.array(portfolio_returns)
		if isinstance(benchmark_returns, (list, pd.Series)):
			benchmark_returns = np.array(benchmark_returns)

		# 计算超额收益
		excess_returns = portfolio_returns - benchmark_returns

		# 过滤掉NaN值
		valid_excess = excess_returns[~np.isnan(excess_returns)]

		if len(valid_excess) < 2:
			return 0.0

		# 计算跟踪误差
		tracking_error = np.std(valid_excess, ddof=1) * np.sqrt(self.trading_days)

		return tracking_error

	def beta (self, portfolio_returns: Union[List[float], np.ndarray, pd.Series],
	          benchmark_returns: Union[List[float], np.ndarray, pd.Series]) -> float:
		"""
		计算Beta系数

		Args:
			portfolio_returns: 组合收益率序列
			benchmark_returns: 基准收益率序列

		Returns:
			float: Beta系数
		"""
		if isinstance(portfolio_returns, (list, pd.Series)):
			portfolio_returns = np.array(portfolio_returns)
		if isinstance(benchmark_returns, (list, pd.Series)):
			benchmark_returns = np.array(benchmark_returns)

		# 过滤掉NaN值
		mask = ~np.isnan(portfolio_returns) & ~np.isnan(benchmark_returns)
		portfolio_returns = portfolio_returns[mask]
		benchmark_returns = benchmark_returns[mask]

		if len(portfolio_returns) < 2 or len(benchmark_returns) < 2:
			return 1.0

		# 计算协方差和方差
		covariance = np.cov(portfolio_returns, benchmark_returns, ddof=1)[0, 1]
		benchmark_variance = np.var(benchmark_returns, ddof=1)

		if benchmark_variance == 0:
			return 1.0

		beta = covariance / benchmark_variance

		return beta

	def alpha (self, portfolio_returns: Union[List[float], np.ndarray, pd.Series],
	           benchmark_returns: Union[List[float], np.ndarray, pd.Series],
	           risk_free_rate: Optional[float] = None) -> float:
		"""
		计算Alpha

		Args:
			portfolio_returns: 组合收益率序列
			benchmark_returns: 基准收益率序列
			risk_free_rate: 无风险利率

		Returns:
			float: Alpha
		"""
		if risk_free_rate is None:
			risk_free_rate = self.risk_free_rate

		# 计算年化收益率
		portfolio_annual_return = self.annualized_return(portfolio_returns)
		benchmark_annual_return = self.annualized_return(benchmark_returns)

		# 计算Beta
		beta_val = self.beta(portfolio_returns, benchmark_returns)

		# 将年化无风险利率转换为与收益率相同的频率
		risk_free_rate_period = (1 + risk_free_rate) ** (1 / self.trading_days) - 1

		# 计算Alpha
		alpha = (portfolio_annual_return - risk_free_rate_period) - \
		        beta_val * (benchmark_annual_return - risk_free_rate_period)

		return alpha

	def jensen_alpha (self, portfolio_returns: Union[List[float], np.ndarray, pd.Series],
	                  benchmark_returns: Union[List[float], np.ndarray, pd.Series],
	                  risk_free_rate: Optional[float] = None) -> float:
		"""
		计算詹森Alpha（与alpha相同）

		Args:
			portfolio_returns: 组合收益率序列
			benchmark_returns: 基准收益率序列
			risk_free_rate: 无风险利率

		Returns:
			float: 詹森Alpha
		"""
		return self.alpha(portfolio_returns, benchmark_returns, risk_free_rate)

	def treynor_ratio (self, portfolio_returns: Union[List[float], np.ndarray, pd.Series],
	                   benchmark_returns: Union[List[float], np.ndarray, pd.Series],
	                   risk_free_rate: Optional[float] = None) -> float:
		"""
		计算特雷诺比率

		Args:
			portfolio_returns: 组合收益率序列
			benchmark_returns: 基准收益率序列
			risk_free_rate: 无风险利率

		Returns:
			float: 特雷诺比率
		"""
		if risk_free_rate is None:
			risk_free_rate = self.risk_free_rate

		# 计算年化收益率
		portfolio_annual_return = self.annualized_return(portfolio_returns)

		# 计算Beta
		beta_val = self.beta(portfolio_returns, benchmark_returns)

		if beta_val == 0:
			return 0.0

		# 将年化无风险利率转换为与收益率相同的频率
		risk_free_rate_period = (1 + risk_free_rate) ** (1 / self.trading_days) - 1

		# 计算特雷诺比率
		treynor = (portfolio_annual_return - risk_free_rate_period) / beta_val

		return treynor

	def calculate_all_metrics (self, prices: Union[List[float], np.ndarray, pd.Series],
	                           benchmark_prices: Optional[Union[List[float], np.ndarray, pd.Series]] = None,
	                           risk_free_rate: Optional[float] = None) -> FinancialMetrics:
		"""
		计算所有金融指标

		Args:
			prices: 价格序列
			benchmark_prices: 基准价格序列
			risk_free_rate: 无风险利率

		Returns:
			FinancialMetrics: 所有金融指标
		"""
		if risk_free_rate is None:
			risk_free_rate = self.risk_free_rate

		# 计算收益率
		returns = self.calculate_returns(prices)
		cumulative_returns = self.cumulative_returns(returns)

		# 基础指标
		annualized_return = self.annualized_return(returns)
		annualized_volatility = self.annualized_volatility(returns)
		sharpe_ratio = self.sharpe_ratio(returns, risk_free_rate)
		sortino_ratio = self.sortino_ratio(returns, risk_free_rate)
		max_drawdown = self.maximum_drawdown(prices)
		max_drawdown_duration = self.drawdown_duration(prices)
		calmar_ratio = self.calmar_ratio(prices, risk_free_rate)
		var_95 = self.value_at_risk(returns, 0.95)
		cvar_95 = self.conditional_value_at_risk(returns, 0.95)
		omega_ratio = self.omega_ratio(returns)

		# 相对指标（如果有基准）
		information_ratio_val = None
		alpha_val = None
		beta_val = None
		tracking_error_val = None
		treynor_ratio_val = None
		jensen_alpha_val = None

		if benchmark_prices is not None:
			benchmark_returns = self.calculate_returns(benchmark_prices)

			information_ratio_val = self.information_ratio(returns, benchmark_returns)
			alpha_val = self.alpha(returns, benchmark_returns, risk_free_rate)
			beta_val = self.beta(returns, benchmark_returns)
			tracking_error_val = self.tracking_error(returns, benchmark_returns)
			treynor_ratio_val = self.treynor_ratio(returns, benchmark_returns, risk_free_rate)
			jensen_alpha_val = self.jensen_alpha(returns, benchmark_returns, risk_free_rate)

		return FinancialMetrics(
			returns=returns,
			cumulative_returns=cumulative_returns,
			annualized_return=annualized_return,
			annualized_volatility=annualized_volatility,
			sharpe_ratio=sharpe_ratio,
			sortino_ratio=sortino_ratio,
			max_drawdown=max_drawdown,
			max_drawdown_duration=max_drawdown_duration,
			calmar_ratio=calmar_ratio,
			var_95=var_95,
			cvar_95=cvar_95,
			omega_ratio=omega_ratio,
			information_ratio=information_ratio_val,
			alpha=alpha_val,
			beta=beta_val,
			tracking_error=tracking_error_val,
			treynor_ratio=treynor_ratio_val,
			jensen_alpha=jensen_alpha_val
		)


# 便捷函数
def calculate_returns (prices: Union[List[float], np.ndarray, pd.Series],
                       return_type: ReturnType = ReturnType.SIMPLE) -> np.ndarray:
	"""计算收益率"""
	return FinancialCalculator().calculate_returns(prices, return_type)


def log_returns (prices: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
	"""计算对数收益率"""
	return FinancialCalculator().log_returns(prices)


def cumulative_returns (returns: Union[List[float], np.ndarray, pd.Series]) -> np.ndarray:
	"""计算累计收益率"""
	return FinancialCalculator().cumulative_returns(returns)


def annualized_return (returns: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算年化收益率"""
	return FinancialCalculator().annualized_return(returns)


def annualized_volatility (returns: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算年化波动率"""
	return FinancialCalculator().annualized_volatility(returns)


def sharpe_ratio (returns: Union[List[float], np.ndarray, pd.Series],
                  risk_free_rate: float = 0.03) -> float:
	"""计算夏普比率"""
	return FinancialCalculator(risk_free_rate=risk_free_rate).sharpe_ratio(returns)


def sortino_ratio (returns: Union[List[float], np.ndarray, pd.Series],
                   risk_free_rate: float = 0.03,
                   target_return: float = 0) -> float:
	"""计算索提诺比率"""
	return FinancialCalculator(risk_free_rate=risk_free_rate).sortino_ratio(
		returns, target_return=target_return)


def calmar_ratio (prices: Union[List[float], np.ndarray, pd.Series],
                  risk_free_rate: float = 0.03) -> float:
	"""计算Calmar比率"""
	return FinancialCalculator(risk_free_rate=risk_free_rate).calmar_ratio(prices)


def maximum_drawdown (prices: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算最大回撤"""
	return FinancialCalculator().maximum_drawdown(prices)


def drawdown_duration (prices: Union[List[float], np.ndarray, pd.Series]) -> int:
	"""计算最大回撤持续时间"""
	return FinancialCalculator().drawdown_duration(prices)


def value_at_risk (returns: Union[List[float], np.ndarray, pd.Series],
                   confidence: float = 0.95) -> float:
	"""计算在险价值"""
	return FinancialCalculator().value_at_risk(returns, confidence)


def conditional_value_at_risk (returns: Union[List[float], np.ndarray, pd.Series],
                               confidence: float = 0.95) -> float:
	"""计算条件在险价值"""
	return FinancialCalculator().conditional_value_at_risk(returns, confidence)


def omega_ratio (returns: Union[List[float], np.ndarray, pd.Series],
                 threshold: float = 0) -> float:
	"""计算Omega比率"""
	return FinancialCalculator().omega_ratio(returns, threshold)


def information_ratio (portfolio_returns: Union[List[float], np.ndarray, pd.Series],
                       benchmark_returns: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算信息比率"""
	return FinancialCalculator().information_ratio(portfolio_returns, benchmark_returns)


def tracking_error (portfolio_returns: Union[List[float], np.ndarray, pd.Series],
                    benchmark_returns: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算跟踪误差"""
	return FinancialCalculator().tracking_error(portfolio_returns, benchmark_returns)


def beta (portfolio_returns: Union[List[float], np.ndarray, pd.Series],
          benchmark_returns: Union[List[float], np.ndarray, pd.Series]) -> float:
	"""计算Beta系数"""
	return FinancialCalculator().beta(portfolio_returns, benchmark_returns)


def alpha (portfolio_returns: Union[List[float], np.ndarray, pd.Series],
           benchmark_returns: Union[List[float], np.ndarray, pd.Series],
           risk_free_rate: float = 0.03) -> float:
	"""计算Alpha"""
	return FinancialCalculator(risk_free_rate=risk_free_rate).alpha(
		portfolio_returns, benchmark_returns)


def jensen_alpha (portfolio_returns: Union[List[float], np.ndarray, pd.Series],
                  benchmark_returns: Union[List[float], np.ndarray, pd.Series],
                  risk_free_rate: float = 0.03) -> float:
	"""计算詹森Alpha"""
	return FinancialCalculator(risk_free_rate=risk_free_rate).jensen_alpha(
		portfolio_returns, benchmark_returns)


def treynor_ratio (portfolio_returns: Union[List[float], np.ndarray, pd.Series],
                   benchmark_returns: Union[List[float], np.ndarray, pd.Series],
                   risk_free_rate: float = 0.03) -> float:
	"""计算特雷诺比率"""
	return FinancialCalculator(risk_free_rate=risk_free_rate).treynor_ratio(
		portfolio_returns, benchmark_returns)