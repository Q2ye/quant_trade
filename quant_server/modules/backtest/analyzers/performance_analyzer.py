# -*- coding: utf-8 -*-
"""
绩效分析器

负责分析策略的绩效指标
"""
import logging
from typing import Dict, List, Any

import numpy as np

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
	"""
	绩效分析器

	负责分析策略的绩效指标
	"""

	def __init__ (self):
		"""
		初始化绩效分析器
		"""
		pass

	def analyze (self, metrics: Dict[str, Any], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""
		分析绩效指标

		Args:
			metrics: 基础绩效指标
			trades: 交易记录

		Returns:
			详细绩效分析结果
		"""
		try:
			logger.info("开始绩效分析")

			# 计算基础指标
			performance = {
				"total_return": metrics.get("total_return", 0),
				"annualized_return": metrics.get("annualized_return", 0),
				"sharpe_ratio": metrics.get("sharpe_ratio", 0),
				"max_drawdown": metrics.get("max_drawdown", 0),
				"win_rate": metrics.get("win_rate", 0),
				"profit_factor": metrics.get("profit_factor", 0),
				"num_trades": metrics.get("num_signals", 0),
				"duration_days": metrics.get("duration_days", 0)
			}

			# 计算交易相关指标
			if trades:
				performance.update(self._analyze_trades(trades))

			# 计算风险调整收益指标
			performance.update(self._calculate_risk_adjusted_returns(metrics))

			logger.info("绩效分析完成")

			return performance
		except Exception as e:
			logger.error(f"绩效分析失败: {str(e)}")
			return {}

	def _analyze_trades (self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
		"""
		分析交易记录

		Args:
			trades: 交易记录

		Returns:
			交易分析结果
		"""
		# 计算交易频率
		trade_dates = [trade["datetime"] for trade in trades]
		trade_dates.sort()

		# 计算平均持有时间
		holding_periods = []
		for i in range(1, len(trade_dates)):
			delta = trade_dates[i] - trade_dates[i - 1]
			holding_periods.append(delta.days if hasattr(delta, "days") else 0)

		avg_holding_period = np.mean(holding_periods) if holding_periods else 0

		# 计算收益分布
		profits = [trade.get("profit", 0) for trade in trades]
		avg_profit = np.mean(profits) if profits else 0
		std_profit = np.std(profits) if profits else 0

		# 计算最大盈利和最大亏损
		max_profit = max(profits) if profits else 0
		max_loss = min(profits) if profits else 0

		return {
			"avg_holding_period": avg_holding_period,
			"avg_profit_per_trade": avg_profit,
			"std_profit_per_trade": std_profit,
			"max_profit": max_profit,
			"max_loss": max_loss
		}

	def _calculate_risk_adjusted_returns (self, metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""
		计算风险调整收益指标

		Args:
			metrics: 基础绩效指标

		Returns:
			风险调整收益指标
		"""
		sharpe_ratio = metrics.get("sharpe_ratio", 0)
		max_drawdown = metrics.get("max_drawdown", 1)
		annualized_return = metrics.get("annualized_return", 0)

		# 计算索提诺比率（假设无风险利率为0）
		sortino_ratio = annualized_return / np.sqrt(metrics.get("downside_deviation", 1)) if metrics.get(
			"downside_deviation", 0) > 0 else 0

		# 计算卡马比率
		calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0

		# 计算信息比率（假设基准收益率为0）
		information_ratio = annualized_return / np.sqrt(metrics.get("tracking_error", 1)) if metrics.get(
			"tracking_error", 0) > 0 else 0

		return {
			"sortino_ratio": sortino_ratio,
			"calmar_ratio": calmar_ratio,
			"information_ratio": information_ratio
		}
