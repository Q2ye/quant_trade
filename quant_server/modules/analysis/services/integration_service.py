#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块集成服务

负责统一调度分析子服务（绩效、风险、归因），响应外部事件并触发相应分析流程。

职责边界：
----------
1. **事件驱动调度** — 接收策略执行、回测完成、交易完成等外部事件，自动触发绩效/风险/归因分析
2. **服务编排** — 协调 PerformanceService、AttributionService 等子服务完成复合分析任务
3. **结果发布** — 分析完成后通过 EventEngine 发布 AnalysisCompleted 系列事件，供前端或其他模块消费
4. **容错处理** — 单个分析失败不影响其他分析继续执行，所有异常通过 logger 记录

与各子 Service 的关系：
-----------------------
- PerformanceService：被 analyze_strategy_performance 和 analyze_strategy_risk 调用
- AttributionService：被 analyze_portfolio_attribution 委托执行归因
- AnalysisEventHandler：用于注册外部事件监听器
- 其他 Service（ComparisonService、TradeAnalysisService）由各自的 Engine 直接调用

事件发布：
---------
分析完成后发布以下事件（通过 event_engine.publish）：
- PerformanceAnalysisCompletedEvent — 策略绩效分析完成
- RiskAnalysisCompletedEvent — 策略风险分析完成
- AttributionAnalysisCompletedEvent — 投资组合归因分析完成

触发条件：
---------
- handle_strategy_executed → 月初至今的绩效分析（日频）
- handle_backtest_completed → 回测区间的绩效 + 风险分析
- handle_trade_completed → 近 30 天绩效分析
"""

import logging
from datetime import date, timedelta
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.events import (
    PerformanceAnalysisCompletedEvent,
    RiskAnalysisCompletedEvent,
    AttributionAnalysisCompletedEvent
)
from modules.analysis.handlers.event_handler import AnalysisEventHandler
from modules.analysis.services.attribution_service import AttributionService

logger = logging.getLogger(__name__)


class AnalysisIntegrationService:
    """分析模块集成服务

    作为分析模块的中央调度器，协调各子服务完成分析任务。
    对外部事件（策略执行、回测完成、交易完成）做出响应，
    自动触发对应的分析流程并通过事件引擎发布结果。

    使用方式：
        service = AnalysisIntegrationService(event_engine, attribution_service=attr_svc)
        await service.handle_backtest_completed(
            strategy_id="xxx", backtest_result={...}, session=db_session
        )
    """

    def __init__(
            self,
            event_engine,
            attribution_service: AttributionService = None
    ):
        """
        初始化集成服务

        Args:
            event_engine: 事件引擎实例，用于发布分析完成事件
            attribution_service: 归因分析服务实例（可选，注入以复用已有的 Repository 连接）
        """
        self.event_engine = event_engine
        self.attribution_service = attribution_service
        self.event_handler = AnalysisEventHandler(event_engine)

    # =========================================================================
    # 公有方法 — 分析任务调度
    # =========================================================================

    async def analyze_strategy_performance(
            self,
            strategy_id: str,
            start_date: date,
            end_date: date,
            session: AsyncSession
    ) -> Dict[str, Any]:
        """分析策略绩效

        委托 PerformanceService 计算完整的绩效指标（收益、风险、Alpha/Beta 等），
        完成后通过 EventEngine 发布 PerformanceAnalysisCompletedEvent。

        Args:
            strategy_id: 策略 ID
            start_date: 分析区间起始日期
            end_date: 分析区间结束日期
            session: 数据库会话（用于创建 PerformanceService）

        Returns:
            Dict[str, Any]: metrics.to_dict() 的完整绩效字典

        Raises:
            Exception: 绩效分析失败时向上抛出（调用方需处理）
        """
        from modules.analysis.services.performance_service import PerformanceService

        try:
            logger.info(f"开始分析策略 {strategy_id} 绩效 [{start_date} ~ {end_date}]")

            # 委托 PerformanceService 计算绩效
            service = PerformanceService(session)
            metrics = await service.calculate_strategy_performance(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date
            )
            result = metrics.to_dict()

            # 发布分析完成事件
            if self.event_engine:
                self.event_engine.publish(PerformanceAnalysisCompletedEvent(
                    strategy_id=strategy_id,
                    start_date=start_date,
                    end_date=end_date,
                    analysis_type="daily",
                    result=result
                ))

            return result
        except Exception as e:
            logger.error(f"分析策略 {strategy_id} 绩效失败: {str(e)}")
            raise

    async def analyze_strategy_risk(
            self,
            strategy_id: str,
            start_date: date,
            end_date: date,
            session: AsyncSession
    ) -> Dict[str, Any]:
        """分析策略风险指标

        在绩效分析基础上，额外计算 VaR（在险价值）、CVaR（条件在险价值）等
        风险管理指标。需要至少 10 个交易日的收益率数据。

        风险指标：
        - volatility：日收益率标准差
        - var_95：95% 置信度 VaR（历史模拟法，取 5% 分位数）
        - cvar_95：95% CVaR = 超过 VaR 的尾部损失的平均值
        - max_drawdown：从 PerformanceMetrics 获取
        - sharpe_ratio：从 PerformanceMetrics 获取

        Args:
            strategy_id: 策略 ID
            start_date: 分析区间起始日期
            end_date: 分析区间结束日期
            session: 数据库会话

        Returns:
            Dict[str, Any]: 含 strategy_id, volatility, var_95, cvar_95,
                           max_drawdown, sharpe_ratio

        Raises:
            Exception: 风险分析失败时向上抛出
        """
        import numpy as np
        from modules.analysis.services.performance_service import PerformanceService

        try:
            logger.info(f"开始分析策略 {strategy_id} 风险 [{start_date} ~ {end_date}]")

            # 先获取绩效指标（含日收益率序列）
            perf_service = PerformanceService(session)
            metrics = await perf_service.calculate_strategy_performance(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date
            )

            daily_returns = np.array(metrics.daily_returns) if metrics.daily_returns else np.array([])

            if len(daily_returns) < 10:
                result = {"strategy_id": strategy_id, "error": "收益数据不足（至少需要 10 个交易日）"}
            else:
                vol = float(np.std(daily_returns, ddof=1))
                var_95 = float(np.percentile(daily_returns, 5))
                result = {
                    "strategy_id": strategy_id,
                    "volatility": vol,
                    "var_95": var_95,
                    "cvar_95": float(daily_returns[daily_returns <= var_95].mean()) if np.any(
                        daily_returns <= var_95) else var_95,
                    "max_drawdown": float(metrics.max_drawdown),
                    "sharpe_ratio": float(metrics.sharpe_ratio),
                }

            # 发布风险分析完成事件
            if self.event_engine:
                self.event_engine.publish(RiskAnalysisCompletedEvent(
                    strategy_id=strategy_id,
                    start_date=start_date,
                    end_date=end_date,
                    risk_type="VaR",
                    result=result
                ))

            return result
        except Exception as e:
            logger.error(f"分析策略 {strategy_id} 风险失败: {str(e)}")
            raise

    async def analyze_portfolio_attribution(
            self,
            portfolio_id: str,
            start_date: date,
            end_date: date,
            attribution_model: str,
    ) -> Dict[str, Any]:
        """分析投资组合归因

        委托 AttributionService 执行因子归因分析。
        若 attribution_service 未注入，使用模拟数据作为回退。

        Args:
            portfolio_id: 投资组合 ID
            start_date: 分析区间起始日期
            end_date: 分析区间结束日期
            attribution_model: 归因模型名称（"Fama-French" 或 "Carhart"）

        Returns:
            Dict[str, Any]: 含 portfolio_id, start_date, end_date, attribution_model,
                           result（含 total_return, factor_attributions, factor_exposures）

        Raises:
            Exception: 归因分析失败时向上抛出
        """
        try:
            logger.info(
                f"开始分析投资组合 {portfolio_id} 归因 "
                f"[{start_date} ~ {end_date}, model={attribution_model}]"
            )

            if self.attribution_service:
                # 有归因服务：执行真实因子归因
                attribution = await self.attribution_service.perform_factor_attribution(
                    portfolio_id=portfolio_id,
                    start_date=start_date,
                    end_date=end_date,
                    factor_model=attribution_model
                )

                result = {
                    "portfolio_id": portfolio_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "attribution_model": attribution_model,
                    "result": {
                        "total_return": float(attribution.total_return),
                        "factor_attributions": {k: float(v) for k, v in attribution.factor_attributions.items()},
                        "factor_exposures": {k: float(v) for k, v in attribution.factor_exposures.items()}
                    }
                }
            else:
                # 无归因服务：返回空结果
                logger.error(
                    f"未注入 AttributionService，无法执行归因分析。"
                    f"生产环境请在 AnalysisIntegrationService 初始化时注入。"
                )
                result = {
                    "portfolio_id": portfolio_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "attribution_model": attribution_model,
                    "error": "AttributionService 未注入，无法执行归因分析",
                    "result": None,
                }

            # 发布归因分析完成事件
            if self.event_engine:
                completed_event = AttributionAnalysisCompletedEvent(
                    portfolio_id=portfolio_id,
                    start_date=start_date,
                    end_date=end_date,
                    attribution_model=attribution_model,
                    result=result
                )
                self.event_engine.publish(completed_event)

            return result

        except Exception as e:
            logger.error(f"分析投资组合 {portfolio_id} 归因失败: {str(e)}")
            raise

    # =========================================================================
    # 事件处理器 — 响应外部模块事件
    # =========================================================================

    async def handle_strategy_executed(
            self,
            strategy_id: str,
            session: AsyncSession = None
    ) -> None:
        """处理策略执行事件 → 自动触发绩效分析

        外部触发：策略引擎完成一轮信号生成和订单提交后。
        分析区间：当月初至今（日频绩效）。

        Args:
            strategy_id: 被执行的策略 ID
            session: 数据库会话（必填，为 None 时跳过分析并记录 warning）
        """
        try:
            logger.info(f"处理策略 {strategy_id} 执行事件 → 触发绩效分析")
            if session is None:
                logger.warning("缺少数据库会话，跳过自动分析触发")
                return

            # 分析区间：当月初至今
            end_date = date.today()
            start_date = end_date.replace(day=1) if end_date.day > 1 else end_date.replace(
                month=end_date.month - 1 if end_date.month > 1 else 12, day=1)

            await self.analyze_strategy_performance(strategy_id, start_date, end_date, session)
        except Exception as e:
            logger.error(f"处理策略 {strategy_id} 执行事件失败: {str(e)}")

    async def handle_backtest_completed(
            self,
            strategy_id: str,
            backtest_result: Dict[str, Any],
            session: AsyncSession = None
    ) -> None:
        """处理回测完成事件 → 自动触发绩效 + 风险分析

        外部触发：回测引擎完成策略回测后。
        分析区间：从 backtest_result 中提取 start_date/end_date。

        Args:
            strategy_id: 回测的策略 ID
            backtest_result: 回测结果字典（需含 start_date 和 end_date 字段）
            session: 数据库会话（必填）
        """
        try:
            logger.info(f"处理策略 {strategy_id} 回测完成事件 → 触发绩效 + 风险分析")
            if session is None:
                logger.warning("缺少数据库会话，跳过自动分析触发")
                return

            # 从回测结果中提取分析区间
            start_date = date.fromisoformat(
                backtest_result.get('start_date', date.today().isoformat())
            )
            end_date = date.fromisoformat(
                backtest_result.get('end_date', date.today().isoformat())
            )

            # 并行触发绩效和风险分析（注意：这里实际上是顺序执行，可优化为并行）
            await self.analyze_strategy_performance(strategy_id, start_date, end_date, session)
            await self.analyze_strategy_risk(strategy_id, start_date, end_date, session)
        except Exception as e:
            logger.error(f"处理策略 {strategy_id} 回测完成事件失败: {str(e)}")

    async def handle_trade_completed(
            self,
            trade_data: Dict[str, Any],
            session: AsyncSession = None
    ) -> None:
        """处理交易完成事件 → 自动触发绩效分析

        外部触发：交易引擎完成订单成交后。
        分析区间：近 30 天。

        Args:
            trade_data: 交易数据字典（需含 strategy_id 字段）
            session: 数据库会话（必填）
        """
        strategy_id = None
        try:
            strategy_id = trade_data.get('strategy_id')
            if not strategy_id:
                logger.warning("交易数据缺少 strategy_id，跳过分析")
                return

            logger.info(f"处理策略 {strategy_id} 交易完成事件 → 触发近 30 天绩效分析")
            if session is None:
                logger.warning("缺少数据库会话，跳过自动分析触发")
                return

            end_date = date.today()
            start_date = end_date - timedelta(days=30)

            await self.analyze_strategy_performance(strategy_id, start_date, end_date, session)
        except Exception as e:
            logger.error(f"处理策略 {strategy_id} 交易完成事件失败: {str(e)}")
