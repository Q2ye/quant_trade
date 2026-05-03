#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略对比服务

负责比较多个策略的绩效表现，提供排名、相关性分析和统计摘要。

核心功能：
----------
1. **多策略对比** — 批量获取策略绩效指标，输出综合排名
2. **按类别对比** — 按策略类型（technical/alpha/ai）分组对比
3. **基准对比** — 单策略 vs 基准指数的相对绩效分析
4. **排名计算** — 多指标排名（收益、夏普、回撤等），自动判断指标方向
5. **相关性分析** — 策略间收益率相关性矩阵，用于组合分散化评估
6. **风险调整排名** — 按夏普比率和索提诺比率排名
7. **洞察与建议** — 基于绩效和相关性自动生成投资建议

排名方向：
- 正向指标（越大越好）：total_return, annual_return, sharpe_ratio, sortino_ratio, win_rate
- 反向指标（越小越好）：max_drawdown
"""

import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.models import PerformanceMetrics
from modules.analysis.models import StrategyComparison
from shared.database.repositories import AccountRepository
from shared.database.repositories import StrategyRepository
from shared.database.repositories.market.quote import StockDailyRepository

logger = logging.getLogger(__name__)


class ComparisonService:
    """策略对比服务

    提供策略间横向对比分析，包括排名、相关性、风险调整后评估。
    依赖 PerformanceService 获取单个策略的绩效指标。

    使用方式：
        service = ComparisonService(session, performance_service=perf_service)
        result = await service.compare_strategies(
            strategy_ids=["s1", "s2"], start_date=..., end_date=...
        )
    """

    def __init__(
            self,
            session: AsyncSession,
            strategy_repo: StrategyRepository = None,
            account_repo: AccountRepository = None,
            performance_service=None,
            quote_repo: StockDailyRepository = None
    ):
        """
        初始化对比服务

        Args:
            session: 异步数据库会话
            strategy_repo: 策略 Repository（可选）
            account_repo: 账户 Repository（可选）
            performance_service: PerformanceService 实例（推荐注入，用于计算策略绩效）
            quote_repo: 日线行情 Repository（用于获取收益率序列计算相关性）
        """
        self.session = session
        self.strategy_repo = strategy_repo or StrategyRepository(session)
        self.account_repo = account_repo or AccountRepository(session)
        self.performance_service = performance_service
        self.quote_repo = quote_repo or StockDailyRepository(session)

    # =========================================================================
    # 公有方法 — 对比分析入口
    # =========================================================================

    async def compare_strategies(
            self,
            strategy_ids: List[str],
            start_date: date,
            end_date: date,
            benchmark: Optional[str] = None,
            metrics_to_rank: List[str] = None
    ) -> StrategyComparison:
        """对比多个策略的综合表现

        计算流程：
        1. 批量获取各策略的 PerformanceMetrics
        2. 按指定指标计算排名
        3. 计算策略间收益率相关性矩阵
        4. 计算各指标的统计摘要（均值/中位数/标准差/最大/最小）
        5. 计算风险调整后排名（夏普比率、索提诺比率）
        6. 生成投资洞察和建议

        Args:
            strategy_ids: 策略 ID 列表（至少 2 个）
            start_date: 分析区间起始日期
            end_date: 分析区间结束日期
            benchmark: 基准指数代码（可选，如 "000300.SH"）
            metrics_to_rank: 需要排名的指标列表，默认为全部核心指标

        Returns:
            StrategyComparison: 包含排名、相关性、统计、洞察和建议的对比结果

        Raises:
            ValueError: 无法获取任何策略的绩效数据时抛出
        """
        try:
            # 1. 获取各策略绩效指标
            performance_metrics = await self._get_strategies_performance(
                strategy_ids, start_date, end_date, benchmark
            )

            if not performance_metrics:
                raise ValueError("无法获取策略绩效数据")

            # 2. 计算各指标排名
            rankings = self._calculate_rankings(
                performance_metrics, metrics_to_rank
            )

            # 3. 计算策略间相关性
            correlations = await self._calculate_correlations(
                strategy_ids, start_date, end_date
            )

            # 4. 计算统计摘要
            statistics = self._calculate_statistics(performance_metrics)

            # 5. 风险调整后排名
            risk_adjusted_rankings = self._calculate_risk_adjusted_rankings(
                performance_metrics
            )

            # 6. 生成洞察和建议
            insights = self._generate_insights(performance_metrics, rankings)
            recommendations = self._generate_recommendations(
                performance_metrics, rankings, correlations
            )

            # 7. 构建对比结果
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

    async def compare_strategies_by_category(
            self,
            category: str,
            start_date: date,
            end_date: date,
            top_n: int = 10,
            benchmark: Optional[str] = None
    ) -> StrategyComparison:
        """按策略类别进行对比分析

        从指定类别中筛选前 N 个策略进行对比。
        支持的类别：'technical'（技术分析）、'alpha'（Alpha 因子）、'ai'（AI/ML）、'all'（全部）

        Args:
            category: 策略类别（'technical', 'alpha', 'ai', 'all'）
            start_date: 起始日期
            end_date: 结束日期
            top_n: 选取前 N 个策略进行对比（默认 10）
            benchmark: 基准指数代码（可选）

        Returns:
            StrategyComparison: 对比结果

        Raises:
            ValueError: 指定类别无策略时抛出
        """
        # 获取指定类别的策略
        if category == 'all':
            strategies = await self.strategy_repo.get_all()
        else:
            strategies = await self.strategy_repo.get_by_category(category)

        if not strategies:
            raise ValueError(f"未找到{category}类别的策略")

        # 取前 top_n 个策略
        strategy_ids = [strategy.id for strategy in strategies[:top_n]]

        return await self.compare_strategies(
            strategy_ids, start_date, end_date, benchmark
        )

    async def compare_with_benchmark(
            self,
            strategy_id: str,
            benchmark_id: str,
            start_date: date,
            end_date: date
    ) -> Dict[str, Any]:
        """将单个策略与基准进行对比

        分别计算策略和基准的绩效指标，然后计算相对绩效（超额收益、风险差异等）。

        Args:
            strategy_id: 策略 ID
            benchmark_id: 基准 ID（如 "000300.SH"）
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            Dict: 含 strategy_id, benchmark_id, strategy_metrics, benchmark_metrics,
                  relative_performance, outperformance（超额收益）

        Raises:
            ValueError: 无法获取策略绩效时抛出
        """
        # 获取策略绩效（以 benchmark_id 为基准）
        strategy_metrics = await self._get_strategy_performance(
            strategy_id, start_date, end_date, benchmark_id
        )

        if not strategy_metrics:
            raise ValueError(f"无法获取策略绩效: {strategy_id}")

        # 获取基准绩效（基准自身的基准为空，避免递归）
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

    # =========================================================================
    # 私有方法 — 数据获取
    # =========================================================================

    async def _get_strategies_performance(
            self,
            strategy_ids: List[str],
            start_date: date,
            end_date: date,
            benchmark: Optional[str] = None
    ) -> Dict[str, PerformanceMetrics]:
        """批量获取多个策略的绩效指标

        优先使用注入的 performance_service 计算；无 performance_service 时
        回退到 _get_strategy_performance 的简化实现。

        单个策略失败不影响其他策略继续计算。

        Args:
            strategy_ids: 策略 ID 列表
            start_date: 起始日期
            end_date: 结束日期
            benchmark: 基准代码（可选）

        Returns:
            Dict[str, PerformanceMetrics]: {strategy_id: metrics}
        """
        performance_metrics = {}

        for strategy_id in strategy_ids:
            try:
                if self.performance_service:
                    metrics = await self.performance_service.calculate_strategy_performance(
                        strategy_id, start_date, end_date, benchmark
                    )
                else:
                    metrics = await self._get_strategy_performance(
                        strategy_id, start_date, end_date, benchmark
                    )

                performance_metrics[strategy_id] = metrics

            except Exception as e:
                logger.warning(f"获取策略 {strategy_id} 绩效失败: {str(e)}")
                continue

        return performance_metrics

    async def _get_strategy_performance(
            self,
            strategy_id: str,
            start_date: date,
            end_date: date,
            benchmark=None
    ) -> 'PerformanceMetrics':
        """获取单个策略的绩效指标（无 PerformanceService 时的回退实现）

        从数据库获取策略基本信息，返回仅含基础字段的 PerformanceMetrics。
        所有绩效值初始化为 0，作为占位结果。

        Args:
            strategy_id: 策略 ID
            start_date: 起始日期
            end_date: 结束日期
            benchmark: 基准代码（可选）

        Returns:
            PerformanceMetrics: 基础绩效指标（收益类字段均为 0）

        Raises:
            ValueError: 策略不存在时抛出
        """
        strategy = await self.strategy_repo.get(strategy_id)
        if not strategy:
            raise ValueError(f'策略 {strategy_id} 不存在')
        total_days = (end_date - start_date).days + 1
        return PerformanceMetrics(
            strategy_id=strategy_id,
            account_id=getattr(strategy, 'user_id', ''),
            start_date=start_date,
            end_date=end_date,
            benchmark=benchmark,
            total_return=Decimal('0.0'),
            annual_return=Decimal('0.0'),
            total_days=total_days,
            trading_days=0,
        )

    async def _get_strategy_returns(
            self,
            strategy_id: str,
            start_date: date,
            end_date: date
    ) -> Optional[pd.Series]:
        """获取策略的日收益率序列

        优先从行情数据获取（通过 quote_repo 获取策略关联的持仓股票日线数据）。
        无法获取真实数据时回退到随机模拟（仅用于开发调试阶段）。

        Args:
            strategy_id: 策略 ID
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            Optional[pd.Series]: 日收益率序列，index=日期，获取失败返回 None

        TODO: 通过 trade_repo 获取策略的实际交易记录，基于交易盈亏和持仓变化
              构建真实的日收益率序列，替代当前随机模拟。
        """
        try:
            # 尝试通过策略的净值曲线获取真实收益率
            strategy = await self.strategy_repo.get(strategy_id)
            if strategy and self.performance_service:
                metrics = await self.performance_service.calculate_strategy_performance(
                    strategy_id, start_date, end_date
                )
                if metrics and metrics.daily_returns:
                    dates = pd.date_range(start_date, end_date, freq='D')
                    returns = pd.Series(metrics.daily_returns[:len(dates)], index=dates[:len(metrics.daily_returns)])
                    return returns

            # 回退：随机模拟（仅开发阶段）
            logger.warning(
                f"策略 {strategy_id} 无法获取真实收益率序列，使用随机模拟数据。"
                f"请确保注入 performance_service 并关联 trade_repo。"
            )
            dates = pd.date_range(start_date, end_date, freq='D')
            np.random.seed(hash(strategy_id) % 10000)
            returns = np.random.randn(len(dates)) * 0.01
            return pd.Series(returns, index=dates)
        except (ValueError, TypeError) as e:
            logger.warning(f"获取策略 {strategy_id} 收益率序列失败: {str(e)}")
            return None

    # =========================================================================
    # 静态方法 — 排名与统计计算
    # =========================================================================

    @staticmethod
    def _calculate_rankings(
            performance_metrics: Dict[str, PerformanceMetrics],
            metrics_to_rank: List[str] = None
    ) -> Dict[str, Dict[str, int]]:
        """计算各指标下的策略排名

        自动判断指标方向：
        - 正向指标（return/sharpe/sortino/win_rate）：值越大排名越前
        - 反向指标（max_drawdown）：值越小排名越前

        Args:
            performance_metrics: 策略绩效字典 {strategy_id: PerformanceMetrics}
            metrics_to_rank: 需要排名的指标列表，默认全部核心指标

        Returns:
            Dict: {metric_name: {strategy_id: rank}}，rank 从 1 开始（1 = 最优）
        """
        if not performance_metrics:
            return {}

        if metrics_to_rank is None:
            metrics_to_rank = [
                'total_return', 'annual_return', 'sharpe_ratio',
                'sortino_ratio', 'max_drawdown', 'win_rate'
            ]

        rankings = {}

        for metric in metrics_to_rank:
            # 提取该指标下各策略的值
            metric_values = {}
            for strategy_id, metrics in performance_metrics.items():
                if hasattr(metrics, metric):
                    value = getattr(metrics, metric)
                    metric_values[strategy_id] = float(value)

            if not metric_values:
                continue

            # 按指标方向排序
            if metric in ['max_drawdown']:
                # 越小越好（回撤）
                sorted_strategies = sorted(
                    metric_values.items(), key=lambda x: x[1]
                )
            else:
                # 越大越好
                sorted_strategies = sorted(
                    metric_values.items(), key=lambda x: x[1], reverse=True
                )

            # 分配排名（1-based）
            metric_rankings = {}
            for rank, (strategy_id, value) in enumerate(sorted_strategies, 1):
                metric_rankings[strategy_id] = rank

            rankings[metric] = metric_rankings

        return rankings

    async def _calculate_correlations(
            self,
            strategy_ids: List[str],
            start_date: date,
            end_date: date
    ) -> Dict[str, Dict[str, Decimal]]:
        """计算策略间收益率相关性矩阵

        使用 Pearson 相关系数衡量策略间的线性相关程度。
        低相关性（<0.3）的策略适合组合以分散风险。

        计算流程：
        1. 获取每个策略的日收益率序列
        2. 对齐数据（取交集日期，删除 NaN）
        3. 计算 DataFrame.corr() 得到相关矩阵
        4. 转换为 Decimal 字典

        Args:
            strategy_ids: 策略 ID 列表
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            Dict: {strategy1: {strategy2: correlation}}，correlation ∈ [-1, 1]
        """
        returns_dict = {}

        for strategy_id in strategy_ids:
            returns = await self._get_strategy_returns(strategy_id, start_date, end_date)
            if returns is not None:
                returns_dict[strategy_id] = returns

        if len(returns_dict) < 2:
            return {}

        # 对齐数据并删除 NaN
        aligned_data = self._align_returns_data(returns_dict)

        if aligned_data.empty:
            return {}

        # 计算 Pearson 相关矩阵
        correlation_matrix = aligned_data.corr()

        # 转换为 Decimal 字典
        correlations = {}
        for strategy1 in correlation_matrix.index:
            correlations[strategy1] = {}
            for strategy2 in correlation_matrix.columns:
                if pd.notna(correlation_matrix.loc[strategy1, strategy2]):
                    correlations[strategy1][strategy2] = Decimal(
                        str(correlation_matrix.loc[strategy1, strategy2])
                    )

        return correlations

    @staticmethod
    def _align_returns_data(returns_dict: Dict[str, pd.Series]) -> pd.DataFrame:
        """对齐多个策略的收益率序列

        将所有策略的收益率序列合并为 DataFrame，只保留所有策略都有数据的日期。
        （dropna 删除任何策略缺失数据的行）

        Args:
            returns_dict: 策略收益率字典 {strategy_id: pd.Series}

        Returns:
            pd.DataFrame: columns=strategy_ids, index=日期, 无 NaN
        """
        if not returns_dict:
            return pd.DataFrame()

        df = pd.DataFrame(returns_dict)
        df = df.dropna()

        return df

    @staticmethod
    def _calculate_statistics(
            performance_metrics: Dict[str, PerformanceMetrics]
    ) -> Dict[str, Dict[str, Any]]:
        """计算绩效指标的统计摘要

        对各指标计算均值、中位数、标准差、最小值和最大值。

        Args:
            performance_metrics: 策略绩效字典

        Returns:
            Dict: {metric: {mean, median, std, min, max, count}}
        """
        if not performance_metrics:
            return {}

        statistics = {}

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

    @staticmethod
    def _calculate_risk_adjusted_rankings(
            performance_metrics: Dict[str, PerformanceMetrics]
    ) -> Dict[str, List[str]]:
        """计算风险调整后排名

        按夏普比率和索提诺比率分别排序，得到风险调整后的策略优先级。
        与原始排名结合使用，避免仅看收益而忽略风险。

        Args:
            performance_metrics: 策略绩效字典

        Returns:
            Dict: {metric: [strategy_id, ...]}，按降序排列
        """
        if not performance_metrics:
            return {}

        risk_adjusted_rankings = {}

        # 夏普比率排名（每单位风险的超额收益）
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

        # 索提诺比率排名（只惩罚下行风险）
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

    @staticmethod
    def _calculate_relative_performance(
            strategy_metrics: PerformanceMetrics,
            benchmark_metrics: PerformanceMetrics
    ) -> Dict[str, Any]:
        """计算策略相对于基准的绩效差异

        对比维度：
        - 超额收益 = 策略总收益 - 基准总收益
        - 风险差异 = 策略最大回撤 - 基准最大回撤
        - 夏普差异 = 策略夏普 - 基准夏普

        Args:
            strategy_metrics: 策略绩效指标
            benchmark_metrics: 基准绩效指标（可为 None）

        Returns:
            Dict: 含 total_return, max_drawdown, sharpe_ratio 的相对差异
        """
        relative = {}

        if strategy_metrics.total_return is not None and benchmark_metrics.total_return is not None:
            relative['total_return'] = float(
                strategy_metrics.total_return - benchmark_metrics.total_return
            )

        if strategy_metrics.max_drawdown is not None and benchmark_metrics.max_drawdown is not None:
            relative['max_drawdown'] = float(
                strategy_metrics.max_drawdown - benchmark_metrics.max_drawdown
            )

        if strategy_metrics.sharpe_ratio is not None and benchmark_metrics.sharpe_ratio is not None:
            relative['sharpe_ratio'] = float(
                strategy_metrics.sharpe_ratio - benchmark_metrics.sharpe_ratio
            )

        return relative

    # =========================================================================
    # 静态方法 — 洞察与建议生成
    # =========================================================================

    @staticmethod
    def _generate_insights(
            performance_metrics: Dict[str, PerformanceMetrics],
            rankings: Dict[str, Dict[str, int]]
    ) -> List[str]:
        """基于绩效和排名生成投资洞察

        自动识别：
        - 最佳收益策略（total_return 排名第一）
        - 最低回撤策略（max_drawdown 排名第一）
        - 最佳夏普比率策略（sharpe_ratio 排名第一）

        Args:
            performance_metrics: 策略绩效字典
            rankings: 排名结果

        Returns:
            List[str]: 洞察描述列表，可直接展示给用户
        """
        insights = []

        if not performance_metrics or not rankings:
            return insights

        # 最佳收益策略
        if 'total_return' in rankings:
            best_strategy = min(
                rankings['total_return'].items(), key=lambda x: x[1]
            )[0]
            best_return = float(performance_metrics[best_strategy].total_return)

            insights.append(
                f"最佳收益策略: {best_strategy}, 总收益: {best_return:.2%}"
            )

        # 最低回撤策略
        if 'max_drawdown' in rankings:
            lowest_risk_strategy = min(
                rankings['max_drawdown'].items(), key=lambda x: x[1]
            )[0]
            lowest_drawdown = float(performance_metrics[lowest_risk_strategy].max_drawdown)

            insights.append(
                f"最低回撤策略: {lowest_risk_strategy}, 最大回撤: {lowest_drawdown:.2%}"
            )

        # 最佳夏普比率策略
        if 'sharpe_ratio' in rankings:
            best_sharpe_strategy = min(
                rankings['sharpe_ratio'].items(), key=lambda x: x[1]
            )[0]
            best_sharpe = float(performance_metrics[best_sharpe_strategy].sharpe_ratio)

            insights.append(
                f"最佳夏普比率策略: {best_sharpe_strategy}, 夏普比率: {best_sharpe:.2f}"
            )

        return insights

    @staticmethod
    def _generate_recommendations(
            performance_metrics: Dict[str, PerformanceMetrics],
            rankings: Dict[str, Dict[str, int]],
            correlations: Dict[str, Dict[str, Decimal]]
    ) -> List[str]:
        """基于绩效和相关性生成投资建议

        建议类型：
        1. 绩效驱动：推荐总收益排名前 3 的策略
        2. 分散化驱动：推荐相关性最低的策略对（correlation < 0.3 适合组合）

        Args:
            performance_metrics: 策略绩效字典
            rankings: 排名结果
            correlations: 策略间相关性矩阵

        Returns:
            List[str]: 建议描述列表
        """
        recommendations = []

        if not performance_metrics:
            return recommendations

        # 绩效建议：推荐前三名
        if len(performance_metrics) >= 3:
            if 'total_return' in rankings:
                top_3 = sorted(
                    rankings['total_return'].items(), key=lambda x: x[1]
                )[:3]
                top_strategies = [s for s, _ in top_3]

                recommendations.append(
                    f"基于总收益，推荐策略: {', '.join(top_strategies)}"
                )

        # 分散化建议：推荐低相关性策略对
        if correlations:
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
