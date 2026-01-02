#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略对比服务

负责比较多个策略的绩效，进行排名、相关性分析等。
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date
import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.models import StrategyComparison
from modules.analysis.models import PerformanceMetrics
from shared.database.repositories.strategy_repo import StrategyRepository
from shared.database.repositories.account_repo import AccountRepository
from core.utils.math_utils.statistic_calculator import StatisticCalculator


class ComparisonService:
	"""策略对比服务"""

	def __init__ (
			self,
			session: AsyncSession,
			strategy_repo: StrategyRepository = None,
			account_repo: AccountRepository = None,
			performance_service=None
	):
		"""
		初始化对比服务

		Args:
			session: 数据库会话
			strategy_repo: 策略Repository
			account_repo: 账户Repository
			performance_service: 绩效服务实例（可选）
		"""
		self.session = session
		self.strategy_repo = strategy_repo or StrategyRepository(session)
		self.account_repo = account_repo or AccountRepository(session)
		self.performance_service = performance_service
		self.stat_calc = StatisticCalculator()

	async def compare_strategies (
			self,
			strategy_ids: List[str],
			start_date: date,
			end_date: date,
			benchmark: Optional[str] = None,
			metrics_to_rank: List[str] = None
	) -> StrategyComparison:
		"""
		对比多个策略

		Args:
			strategy_ids: 策略ID列表
			start_date: 开始日期
			end_date: 结束日期
			benchmark: 基准代码
			metrics_to_rank: 需要排名的指标列表

		Returns:
			StrategyComparison: 策略对比结果
		"""
		try:
			# 获取各策略的绩效指标
			performance_metrics = await self._get_strategies_performance(
				strategy_ids, start_date, end_date, benchmark
			)

			if not performance_metrics:
				raise ValueError("无法获取策略绩效数据")

			# 计算排名
			rankings = self._calculate_rankings(
				performance_metrics, metrics_to_rank
			)

			# 计算相关性
			correlations = await self._calculate_correlations(
				strategy_ids, start_date, end_date
			)

			# 计算统计量
			statistics = self._calculate_statistics(performance_metrics)

			# 风险调整后排名
			risk_adjusted_rankings = self._calculate_risk_adjusted_rankings(
				performance_metrics
			)

			# 生成洞察和建议
			insights = self._generate_insights(performance_metrics, rankings)
			recommendations = self._generate_recommendations(
				performance_metrics, rankings, correlations
			)

			# 构建对比对象
			comparison = StrategyComparison(
				comparison_id=f"comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
				strategy_ids=strategy_ids,
				comparison_date=date.today(),
				benchmark=benchmark,
				performance_comparison=performance_metrics,
				rankings=rankings,
				correlations=correlations,
				statistics=statistics,
				risk_adjusted_rankings=risk_adjusted_rankings,
				insights=insights,
				recommendations=recommendations
			)

			return comparison

		except Exception as e:
			raise ValueError(f"策略对比失败: {str(e)}")

	async def compare_strategies_by_category (
			self,
			category: str,
			start_date: date,
			end_date: date,
			top_n: int = 10,
			benchmark: Optional[str] = None
	) -> StrategyComparison:
		"""
		按类别对比策略

		Args:
			category: 策略类别 ('technical', 'alpha', 'ai', 'all')
			start_date: 开始日期
			end_date: 结束日期
			top_n: 返回前N个策略
			benchmark: 基准代码

		Returns:
			StrategyComparison: 策略对比结果
		"""
		# 获取指定类别的策略
		if category == 'all':
			strategies = await self.strategy_repo.get_all()
		else:
			strategies = await self.strategy_repo.get_by_category(category)

		if not strategies:
			raise ValueError(f"未找到{category}类别的策略")

		# 只取前top_n个策略
		strategy_ids = [strategy.id for strategy in strategies[:top_n]]

		return await self.compare_strategies(
			strategy_ids, start_date, end_date, benchmark
		)

	async def compare_with_benchmark (
			self,
			strategy_id: str,
			benchmark_id: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		策略与基准对比

		Args:
			strategy_id: 策略ID
			benchmark_id: 基准ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			对比结果
		"""
		# 获取策略绩效
		strategy_metrics = await self._get_strategy_performance(
			strategy_id, start_date, end_date, benchmark_id
		)

		if not strategy_metrics:
			raise ValueError(f"无法获取策略绩效: {strategy_id}")

		# 获取基准绩效（基准自身的基准为空）
		benchmark_metrics = await self._get_strategy_performance(
			benchmark_id, start_date, end_date, None
		)

		# 计算相对绩效
		relative_performance = self._calculate_relative_performance(
			strategy_metrics, benchmark_metrics
		)

		return {
			'strategy_id': strategy_id,
			'benchmark_id': benchmark_id,
			'strategy_metrics': strategy_metrics.to_dict(),
			'benchmark_metrics': benchmark_metrics.to_dict() if benchmark_metrics else None,
			'relative_performance': relative_performance,
			'outperformance': strategy_metrics.total_return - (
				benchmark_metrics.total_return if benchmark_metrics else Decimal("0.0"))
		}

	async def _get_strategies_performance (
			self,
			strategy_ids: List[str],
			start_date: date,
			end_date: date,
			benchmark: Optional[str] = None
	) -> Dict[str, PerformanceMetrics]:
		"""
		获取多个策略的绩效指标

		Args:
			strategy_ids: 策略ID列表
			start_date: 开始日期
			end_date: 结束日期
			benchmark: 基准代码

		Returns:
			策略绩效字典 {strategy_id: PerformanceMetrics}
		"""
		performance_metrics = {}

		# 使用绩效服务计算每个策略的绩效
		for strategy_id in strategy_ids:
			try:
				if self.performance_service:
					metrics = await self.performance_service.calculate_strategy_performance(
						strategy_id, start_date, end_date, benchmark
					)
				else:
					# 简化实现
					metrics = await self._get_strategy_performance(
						strategy_id, start_date, end_date, benchmark
					)

				performance_metrics[strategy_id] = metrics

			except Exception as e:
				print(f"获取策略 {strategy_id} 绩效失败: {str(e)}")
				continue

		return performance_metrics

	def _calculate_rankings (
			self,
			performance_metrics: Dict[str, PerformanceMetrics],
			metrics_to_rank: List[str] = None
	) -> Dict[str, Dict[str, int]]:
		"""
		计算策略排名

		Args:
			performance_metrics: 策略绩效字典
			metrics_to_rank: 需要排名的指标列表

		Returns:
			排名字典 {metric: {strategy_id: rank}}
		"""
		if not performance_metrics:
			return {}

		# 默认排名指标
		if metrics_to_rank is None:
			metrics_to_rank = [
				'total_return', 'annual_return', 'sharpe_ratio',
				'sortino_ratio', 'max_drawdown', 'win_rate'
			]

		rankings = {}

		for metric in metrics_to_rank:
			# 获取所有策略在该指标上的值
			metric_values = {}
			for strategy_id, metrics in performance_metrics.items():
				if hasattr(metrics, metric):
					value = getattr(metrics, metric)
					metric_values[strategy_id] = float(value)

			if not metric_values:
				continue

			# 排序（有些指标越大越好，有些越小越好）
			if metric in ['max_drawdown']:
				# 越小越好
				sorted_strategies = sorted(
					metric_values.items(), key=lambda x: x[1]
				)
			else:
				# 越大越好
				sorted_strategies = sorted(
					metric_values.items(), key=lambda x: x[1], reverse=True
				)

			# 分配排名
			metric_rankings = {}
			for rank, (strategy_id, value) in enumerate(sorted_strategies, 1):
				metric_rankings[strategy_id] = rank

			rankings[metric] = metric_rankings

		return rankings

	async def _calculate_correlations (
			self,
			strategy_ids: List[str],
			start_date: date,
			end_date: date
	) -> Dict[str, Dict[str, Decimal]]:
		"""
		计算策略间的相关性

		Args:
			strategy_ids: 策略ID列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			相关性矩阵 {strategy1: {strategy2: correlation}}
		"""
		# 获取策略的收益率序列
		returns_dict = {}

		for strategy_id in strategy_ids:
			returns = await self._get_strategy_returns(strategy_id, start_date, end_date)
			if returns is not None:
				returns_dict[strategy_id] = returns

		if len(returns_dict) < 2:
			return {}

		# 对齐数据
		aligned_data = self._align_returns_data(returns_dict)

		if aligned_data.empty:
			return {}

		# 计算相关性矩阵
		correlation_matrix = aligned_data.corr()

		# 转换为Decimal字典
		correlations = {}
		for strategy1 in correlation_matrix.index:
			correlations[strategy1] = {}
			for strategy2 in correlation_matrix.columns:
				if pd.notna(correlation_matrix.loc[strategy1, strategy2]):
					correlations[strategy1][strategy2] = Decimal(
						str(correlation_matrix.loc[strategy1, strategy2])
					)

		return correlations

	def _calculate_statistics (
			self,
			performance_metrics: Dict[str, PerformanceMetrics]
	) -> Dict[str, Dict[str, Any]]:
		"""
		计算统计量

		Args:
			performance_metrics: 策略绩效字典

		Returns:
			统计量字典
		"""
		if not performance_metrics:
			return {}

		statistics = {}

		# 为每个指标计算统计量
		metrics_to_analyze = [
			'total_return', 'annual_return', 'sharpe_ratio',
			'max_drawdown', 'volatility', 'win_rate'
		]

		for metric in metrics_to_analyze:
			values = []
			for strategy_id, metrics in performance_metrics.items():
				if hasattr(metrics, metric):
					value = getattr(metrics, metric)
					values.append(float(value))

			if values:
				statistics[metric] = {
					'mean': np.mean(values),
					'median': np.median(values),
					'std': np.std(values),
					'min': np.min(values),
					'max': np.max(values),
					'count': len(values)
				}

		return statistics

	def _calculate_risk_adjusted_rankings (
			self,
			performance_metrics: Dict[str, PerformanceMetrics]
	) -> Dict[str, List[str]]:
		"""
		计算风险调整后排名

		Args:
			performance_metrics: 策略绩效字典

		Returns:
			风险调整后排名 {metric: [strategy_id, ...]}
		"""
		if not performance_metrics:
			return {}

		risk_adjusted_rankings = {}

		# 夏普比率排名
		sharpe_values = {}
		for strategy_id, metrics in performance_metrics.items():
			sharpe_values[strategy_id] = float(metrics.sharpe_ratio)

		if sharpe_values:
			sorted_sharpe = sorted(
				sharpe_values.items(), key=lambda x: x[1], reverse=True
			)
			risk_adjusted_rankings['sharpe_ratio'] = [
				strategy_id for strategy_id, _ in sorted_sharpe
			]

		# 索提诺比率排名
		sortino_values = {}
		for strategy_id, metrics in performance_metrics.items():
			sortino_values[strategy_id] = float(metrics.sortino_ratio)

		if sortino_values:
			sorted_sortino = sorted(
				sortino_values.items(), key=lambda x: x[1], reverse=True
			)
			risk_adjusted_rankings['sortino_ratio'] = [
				strategy_id for strategy_id, _ in sorted_sortino
			]

		return risk_adjusted_rankings

	def _generate_insights (
			self,
			performance_metrics: Dict[str, PerformanceMetrics],
			rankings: Dict[str, Dict[str, int]]
	) -> List[str]:
		"""
		生成洞察

		Args:
			performance_metrics: 策略绩效
			rankings: 策略排名

		Returns:
			洞察列表
		"""
		insights = []

		if not performance_metrics or not rankings:
			return insights

		# 分析最佳策略
		if 'total_return' in rankings:
			best_strategy = min(
				rankings['total_return'].items(), key=lambda x: x[1]
			)[0]
			best_return = float(performance_metrics[best_strategy].total_return)

			insights.append(
				f"最佳收益策略: {best_strategy}, 总收益: {best_return:.2%}"
			)

		# 分析风险最低的策略
		if 'max_drawdown' in rankings:
			lowest_risk_strategy = min(
				rankings['max_drawdown'].items(), key=lambda x: x[1]
			)[0]
			lowest_drawdown = float(performance_metrics[lowest_risk_strategy].max_drawdown)

			insights.append(
				f"最低回撤策略: {lowest_risk_strategy}, 最大回撤: {lowest_drawdown:.2%}"
			)

		# 分析夏普比率最高的策略
		if 'sharpe_ratio' in rankings:
			best_sharpe_strategy = min(
				rankings['sharpe_ratio'].items(), key=lambda x: x[1]
			)[0]
			best_sharpe = float(performance_metrics[best_sharpe_strategy].sharpe_ratio)

			insights.append(
				f"最佳夏普比率策略: {best_sharpe_strategy}, 夏普比率: {best_sharpe:.2f}"
			)

		return insights

	def _generate_recommendations (
			self,
			performance_metrics: Dict[str, PerformanceMetrics],
			rankings: Dict[str, Dict[str, int]],
			correlations: Dict[str, Dict[str, Decimal]]
	) -> List[str]:
		"""
		生成建议

		Args:
			performance_metrics: 策略绩效
			rankings: 策略排名
			correlations: 策略相关性

		Returns:
			建议列表
		"""
		recommendations = []

		if not performance_metrics:
			return recommendations

		# 基于绩效的建议
		if len(performance_metrics) >= 3:
			# 推荐前3名策略
			if 'total_return' in rankings:
				top_3 = sorted(
					rankings['total_return'].items(), key=lambda x: x[1]
				)[:3]
				top_strategies = [s for s, _ in top_3]

				recommendations.append(
					f"基于总收益，推荐策略: {', '.join(top_strategies)}"
				)

		# 基于相关性的建议（推荐低相关性的策略组合）
		if correlations:
			# 找到相关性最低的策略对
			min_corr = 1.0
			min_pair = None

			for strategy1, corr_dict in correlations.items():
				for strategy2, corr in corr_dict.items():
					if strategy1 != strategy2:
						corr_value = float(corr)
						if corr_value < min_corr:
							min_corr = corr_value
							min_pair = (strategy1, strategy2)

			if min_pair and min_corr < 0.3:
				recommendations.append(
					f"策略 {min_pair[0]} 和 {min_pair[1]} 相关性较低 ({min_corr:.2f})，"
					f"适合组合以分散风险"
				)

		return recommendations

	async def _get_strategy_returns (
			self,
			strategy_id: str,
			start_date: date,
			end_date: date
	) -> Optional[pd.Series]:
		"""
		获取策略收益率序列

		Args:
			strategy_id: 策略ID
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			收益率序列
		"""
		# 简化实现：返回模拟数据
		try:
			# 实际应用中应从数据库获取
			dates = pd.date_range(start_date, end_date, freq='D')
			np.random.seed(hash(strategy_id) % 10000)
			returns = np.random.randn(len(dates)) * 0.01

			return pd.Series(returns, index=dates)
		except:
			return None

	def _align_returns_data (
			self,
			returns_dict: Dict[str, pd.Series]
	) -> pd.DataFrame:
		"""
		对齐收益率数据

		Args:
			returns_dict: 收益率字典

		Returns:
			对齐后的DataFrame
		"""
		if not returns_dict:
			return pd.DataFrame()

		# 转换为DataFrame
		df = pd.DataFrame(returns_dict)

		# 删除包含NaN的行
		df = df.dropna()

		return df

	def _calculate_relative_performance (
			self,
			strategy_metrics: PerformanceMetrics,
			benchmark_metrics: PerformanceMetrics
	) -> Dict[str, Any]:
		"""
		计算相对绩效

		Args:
			strategy_metrics: 策略绩效
			benchmark_metrics: 基准绩效

		Returns:
			相对绩效指标
		"""
		relative = {}

		# 收益相对表现
		if strategy_metrics.total_return is not None and benchmark_metrics.total_return is not None:
			relative['total_return'] = float(
				strategy_metrics.total_return - benchmark_metrics.total_return
			)

		# 风险相对表现
		if strategy_metrics.max_drawdown is not None and benchmark_metrics.max_drawdown is not None:
			relative['max_drawdown'] = float(
				strategy_metrics.max_drawdown - benchmark_metrics.max_drawdown
			)

		# 夏普比率相对表现
		if strategy_metrics.sharpe_ratio is not None and benchmark_metrics.sharpe_ratio is not None:
			relative['sharpe_ratio'] = float(
				strategy_metrics.sharpe_ratio - benchmark_metrics.sharpe_ratio
			)

		return relative