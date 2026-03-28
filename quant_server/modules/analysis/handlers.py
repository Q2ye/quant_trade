#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块处理函数

负责绩效归因、风险分析、对比分析等业务逻辑处理。
包含以下处理器：
1. PerformanceAnalysisHandler - 绩效分析处理器
2. RiskAnalysisHandler - 风险分析处理器
3. ComparisonAnalysisHandler - 对比分析处理器
4. AttributionAnalysisHandler - 归因分析处理器
5. TradeAnalysisHandler - 交易分析处理器

注意：顶层的异步函数是API路由层和handler类之间的适配器
"""

import logging
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, func, desc, extract

from quant_server.shared.database.repositories import (
    StrategyRepository,
    OrderRepository,
    TradeRepository,
    PositionRepository,
    AccountRepository
)
from quant_server.shared.database.repositories.account.asset import (
    AccountDailyPerformanceRepository,
    StrategyDailyPerformanceRepository
)
from quant_server.modules.analysis import models as analysis_models
from quant_server.core.exceptions import (
    AnalysisException,
    PermissionException,
    DataNotFoundException
)

# 配置日志
logger = logging.getLogger(__name__)


class BaseAnalysisHandler:
    """分析处理器基类"""

    def __init__(self, db: Session, user_id: str):
        """
        初始化分析处理器基类

        Args:
            db: 数据库会话
            user_id: 用户ID
        """
        self.db = db
        self.user_id = user_id

        # 初始化Repository
        self.strategy_repo = StrategyRepository(db)
        self.order_repo = OrderRepository(db)
        self.trade_repo = TradeRepository(db)
        self.position_repo = PositionRepository(db)
        self.account_repo = AccountRepository(db)
        self.account_performance_repo = AccountDailyPerformanceRepository(db)
        self.strategy_performance_repo = StrategyDailyPerformanceRepository(db)

    def _check_permission(self, resource_id: str, resource_type: str) -> bool:
        """
        检查用户对资源的访问权限

        Args:
            resource_id: 资源ID
            resource_type: 资源类型 (strategy, account, portfolio)

        Returns:
            是否有访问权限

        Raises:
            PermissionException: 没有访问权限
        """
        # TODO: 实现具体的权限检查逻辑
        # 这里简化处理，假设用户只能访问自己的资源
        if resource_type == "strategy":
            strategy = self.strategy_repo.get_by_id(resource_id)
            if strategy and strategy.user_id == self.user_id:
                return True
        elif resource_type == "account":
            account = self.account_repo.get_by_id(resource_id)
            if account and account.user_id == self.user_id:
                return True
        elif resource_type == "portfolio":
            # 假设投资组合也通过用户ID关联
            return True

        raise PermissionException(f"没有访问 {resource_type}: {resource_id} 的权限")

    def _validate_date_range(self, start_date: date, end_date: date) -> Tuple[date, date]:
        """
        验证并调整日期范围

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            调整后的(开始日期, 结束日期)
        """
        # 确保结束日期不晚于今天
        today = date.today()
        if end_date > today:
            end_date = today

        # 确保开始日期不晚于结束日期
        if start_date > end_date:
            start_date = end_date - timedelta(days=365)

        # 确保日期范围不超过5年
        max_days = 365 * 5
        if (end_date - start_date).days > max_days:
            start_date = end_date - timedelta(days=max_days)

        return start_date, end_date


class PerformanceAnalysisHandler(BaseAnalysisHandler):
    """绩效分析处理器"""

    def get_strategy_performance(self, strategy_id: str, start_date: date,
                                 end_date: date, frequency: str = "daily",
                                 include_trades: bool = False) -> Dict[str, Any]:
        """
        获取策略绩效报告

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期
            frequency: 频率 (daily, weekly, monthly)
            include_trades: 是否包含交易明细

        Returns:
            策略绩效报告
        """
        try:
            # 检查权限
            self._check_permission(strategy_id, "strategy")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取策略信息
            strategy = self.strategy_repo.get_by_id(strategy_id)
            if not strategy:
                raise DataNotFoundException(f"策略不存在: {strategy_id}")

            # 获取账户信息
            accounts = self.account_repo.get_by_user_id(self.user_id)
            if not accounts:
                raise DataNotFoundException("用户没有账户")

            # 获取交易数据
            trades = self.trade_repo.get_by_strategy_and_date(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date
            )

            if not trades:
                raise DataNotFoundException(f"策略 {strategy_id} 在指定日期范围内没有交易")

            # 计算绩效指标
            performance_metrics = self._calculate_performance_metrics(
                trades=trades,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency
            )

            # 构建响应
            result = {
                "strategy": {
                    "id": strategy.id,
                    "name": strategy.name,
                    "description": strategy.description
                },
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "trading_days": performance_metrics.trading_days,
                    "total_days": performance_metrics.total_days
                },
                "performance_metrics": performance_metrics.to_dict(),
                "equity_curve": performance_metrics.equity_curve,
                "drawdown_curve": performance_metrics.drawdown_curve
            }

            # 如果包含交易明细
            if include_trades:
                result["trades"] = [
                    {
                        "trade_id": trade.id,
                        "symbol": trade.symbol,
                        "direction": trade.direction,
                        "price": float(trade.price),
                        "volume": trade.volume,
                        "trade_time": trade.trade_time.isoformat(),
                        "pnl": float(trade.pnl) if hasattr(trade, 'pnl') else None
                    }
                    for trade in trades
                ]

            return result

        except Exception as e:
            logger.error(f"获取策略绩效失败: {str(e)}")
            raise AnalysisException(f"获取策略绩效失败: {str(e)}")

    def get_account_performance(self, account_id: str, start_date: date,
                                 end_date: date, benchmark: Optional[str] = None) -> Dict[str, Any]:
        """
        获取账户绩效报告

        Args:
            account_id: 账户ID
            start_date: 开始日期
            end_date: 结束日期
            benchmark: 基准代码

        Returns:
            账户绩效报告
        """
        try:
            # 检查权限
            self._check_permission(account_id, "account")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取账户信息
            account = self.account_repo.get_by_id(account_id)
            if not account:
                raise DataNotFoundException(f"账户不存在: {account_id}")

            # 获取持仓数据
            positions = self.position_repo.get_by_account_and_date(
                account_id=account_id,
                date=end_date
            )

            # 获取交易数据
            trades = self.trade_repo.get_by_account_and_date(
                account_id=account_id,
                start_date=start_date,
                end_date=end_date
            )

            # 获取账户净值曲线
            equity_curve = self.performance_repo.get_equity_curve(
                account_id=account_id,
                start_date=start_date,
                end_date=end_date
            )

            # 计算绩效指标
            performance_metrics = self._calculate_account_performance(
                account=account,
                positions=positions,
                trades=trades,
                equity_curve=equity_curve,
                start_date=start_date,
                end_date=end_date,
                benchmark=benchmark
            )

            # 构建响应
            result = {
                "account": {
                    "id": account.id,
                    "name": account.name,
                    "account_type": account.account_type
                },
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "trading_days": performance_metrics.trading_days,
                    "total_days": performance_metrics.total_days
                },
                "performance_metrics": performance_metrics.to_dict(),
                "asset_allocation": self._calculate_asset_allocation(positions),
                "top_positions": self._get_top_positions(positions, limit=10),
                "recent_trades": self._get_recent_trades(trades, limit=20)
            }

            return result

        except Exception as e:
            logger.error(f"获取账户绩效失败: {str(e)}")
            raise AnalysisException(f"获取账户绩效失败: {str(e)}")

    def _calculate_performance_metrics(self, trades: List, start_date: date,
                                        end_date: date, frequency: str) -> analysis_models.PerformanceMetrics:
        """
        计算绩效指标

        Args:
            trades: 交易列表
            start_date: 开始日期
            end_date: 结束日期
            frequency: 频率

        Returns:
            绩效指标对象
        """
        # TODO: 实现具体的绩效指标计算逻辑
        # 这里返回一个示例对象
        return analysis_models.PerformanceMetrics(
            strategy_id="sample_strategy_id",
            account_id="sample_account_id",
            start_date=start_date,
            end_date=end_date,
            total_return=Decimal("0.15"),  # 15%
            annual_return=Decimal("0.12"),  # 12%
            volatility=Decimal("0.20"),  # 20%
            sharpe_ratio=Decimal("0.6"),
            max_drawdown=Decimal("0.08"),  # 8%
            win_rate=Decimal("0.55"),  # 55%
            total_trades=len(trades),
            trading_days=180,
            total_days=(end_date - start_date).days
        )

    def _calculate_account_performance(self, account, positions, trades,
                                        equity_curve, start_date, end_date, benchmark):
        """
        计算账户绩效指标

        Args:
            account: 账户对象
            positions: 持仓列表
            trades: 交易列表
            equity_curve: 净值曲线
            start_date: 开始日期
            end_date: 结束日期
            benchmark: 基准代码

        Returns:
            绩效指标对象
        """
        # TODO: 实现具体的账户绩效计算逻辑
        return analysis_models.PerformanceMetrics(
            strategy_id="account_performance",
            account_id=account.id,
            start_date=start_date,
            end_date=end_date,
            total_return=Decimal("0.10"),  # 10%
            annual_return=Decimal("0.08"),  # 8%
            volatility=Decimal("0.15"),  # 15%
            sharpe_ratio=Decimal("0.53"),
            max_drawdown=Decimal("0.05"),  # 5%
            win_rate=Decimal("0.52"),  # 52%
            total_trades=len(trades),
            trading_days=180,
            total_days=(end_date - start_date).days
        )

    def _calculate_asset_allocation(self, positions: List) -> Dict[str, Any]:
        """
        计算资产配置

        Args:
            positions: 持仓列表

        Returns:
            资产配置信息
        """
        # 简化实现
        total_value = sum(position.market_value for position in positions)

        allocation = {}
        for position in positions:
            if position.market_value > 0:
                allocation[position.symbol] = {
                    "weight": float(position.market_value / total_value),
                    "value": float(position.market_value)
                }

        return allocation

    def _get_top_positions(self, positions: List, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取前N大持仓

        Args:
            positions: 持仓列表
            limit: 限制数量

        Returns:
            前N大持仓列表
        """
        sorted_positions = sorted(positions, key=lambda x: x.market_value, reverse=True)

        return [
            {
                "symbol": position.symbol,
                "market_value": float(position.market_value),
                "pnl": float(position.pnl) if hasattr(position, 'pnl') else 0.0,
                "weight": float(position.market_value / sum(p.market_value for p in positions))
            }
            for position in sorted_positions[:limit]
        ]

    def _get_recent_trades(self, trades: List, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近交易

        Args:
            trades: 交易列表
            limit: 限制数量

        Returns:
            最近交易列表
        """
        sorted_trades = sorted(trades, key=lambda x: x.trade_time, reverse=True)

        return [
            {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "direction": trade.direction,
                "price": float(trade.price),
                "volume": trade.volume,
                "trade_time": trade.trade_time.isoformat()
            }
            for trade in sorted_trades[:limit]
        ]

    async def generate_performance_report_async(self, task_id: str, request: Dict[str, Any]):
        """
        异步生成绩效报告

        Args:
            task_id: 任务ID
            request: 生成报告请求
        """
        try:
            logger.info(f"开始生成绩效报告，任务ID: {task_id}")

            # TODO: 实现异步报告生成逻辑
            # 这里模拟一个长时间运行的任务
            await asyncio.sleep(5)  # 模拟处理时间

            logger.info(f"绩效报告生成完成，任务ID: {task_id}")

        except Exception as e:
            logger.error(f"生成绩效报告失败: {str(e)}")
            raise AnalysisException(f"生成绩效报告失败: {str(e)}")


# ==================== 顶层适配器函数 ====================

async def get_strategy_performance(session: AsyncSession, strategy_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    获取策略绩效报告 - 顶层适配器函数

    Args:
        session: 异步数据库会话
        strategy_id: 策略ID
        request: 请求参数
        user_id: 用户ID

    Returns:
        策略绩效报告
    """
    # 将异步会话转换为同步会话
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = PerformanceAnalysisHandler(sync_session, user_id)
    return handler.get_strategy_performance(
        strategy_id=strategy_id,
        start_date=request.start_date,
        end_date=request.end_date,
        frequency=getattr(request, 'frequency', 'daily'),
        include_trades=getattr(request, 'include_trades', False)
    )

async def get_account_performance(session: AsyncSession, account_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    获取账户绩效报告 - 顶层适配器函数

    Args:
        session: 异步数据库会话
        account_id: 账户ID
        request: 请求参数
        user_id: 用户ID

    Returns:
        账户绩效报告
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = PerformanceAnalysisHandler(sync_session, user_id)
    return handler.get_account_performance(
        account_id=account_id,
        start_date=request.start_date,
        end_date=request.end_date,
        benchmark=getattr(request, 'benchmark', None)
    )

# 继续添加其他适配器函数...

class RiskAnalysisHandler(BaseAnalysisHandler):
    """风险分析处理器"""

    def get_strategy_risk_metrics(self, strategy_id: str, start_date: date,
                                     end_date: date, confidence_level: float = 0.95,
                                     lookback_period: int = 252) -> Dict[str, Any]:
        """
        计算策略风险指标

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期
            confidence_level: 置信水平
            lookback_period: 回看周期

        Returns:
            策略风险指标
        """
        try:
            # 检查权限
            self._check_permission(strategy_id, "strategy")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取策略信息
            strategy = self.strategy_repo.get_by_id(strategy_id)
            if not strategy:
                raise DataNotFoundException(f"策略不存在: {strategy_id}")

            # 获取策略收益数据
            returns_data = self._get_strategy_returns(strategy_id, start_date, end_date)

            if not returns_data:
                raise DataNotFoundException(f"策略 {strategy_id} 在指定日期范围内没有收益数据")

            # 计算风险指标
            risk_metrics = self._calculate_risk_metrics(
                returns_data=returns_data,
                confidence_level=confidence_level,
                lookback_period=lookback_period
            )

            # 构建响应
            result = {
                "strategy": {
                    "id": strategy.id,
                    "name": strategy.name
                },
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "parameters": {
                    "confidence_level": confidence_level,
                    "lookback_period": lookback_period
                },
                "risk_metrics": risk_metrics.to_dict()
            }

            return result

        except Exception as e:
            logger.error(f"计算策略风险指标失败: {str(e)}")
            raise AnalysisException(f"计算策略风险指标失败: {str(e)}")

    def get_portfolio_risk(self, portfolio_id: str, start_date: date,
                            end_date: date, risk_model: str = "covariance") -> Dict[str, Any]:
        """
        分析投资组合风险

        Args:
            portfolio_id: 投资组合ID
            start_date: 开始日期
            end_date: 结束日期
            risk_model: 风险模型

        Returns:
            投资组合风险分析结果
        """
        try:
            # 检查权限
            self._check_permission(portfolio_id, "portfolio")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取投资组合数据
            portfolio_data = self._get_portfolio_data(portfolio_id, start_date, end_date)

            if not portfolio_data:
                raise DataNotFoundException(f"投资组合 {portfolio_id} 在指定日期范围内没有数据")

            # 根据风险模型计算风险
            if risk_model == "covariance":
                risk_analysis = self._calculate_covariance_risk(portfolio_data)
            elif risk_model == "historical":
                risk_analysis = self._calculate_historical_risk(portfolio_data)
            elif risk_model == "monte_carlo":
                risk_analysis = self._calculate_monte_carlo_risk(portfolio_data)
            else:
                raise AnalysisException(f"不支持的风险模型: {risk_model}")

            # 构建响应
            result = {
                "portfolio_id": portfolio_id,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "risk_model": risk_model,
                "risk_analysis": risk_analysis
            }

            return result

        except Exception as e:
            logger.error(f"分析投资组合风险失败: {str(e)}")
            raise AnalysisException(f"分析投资组合风险失败: {str(e)}")

    def run_stress_test(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行压力测试

        Args:
            request: 压力测试请求

        Returns:
            压力测试结果
        """
        try:
            portfolio_id = request.get("portfolio_id")
            scenarios = request.get("scenarios", [])

            if not portfolio_id:
                raise AnalysisException("缺少投资组合ID")

            if not scenarios:
                raise AnalysisException("至少需要一个压力测试场景")

            # 检查权限
            self._check_permission(portfolio_id, "portfolio")

            # 获取当前投资组合状态
            portfolio_state = self._get_portfolio_current_state(portfolio_id)

            # 对每个场景执行压力测试
            results = []
            for scenario in scenarios:
                scenario_result = self._run_single_stress_test(
                    portfolio_state=portfolio_state,
                    scenario=scenario
                )
                results.append(scenario_result)

            # 构建响应
            result = {
                "portfolio_id": portfolio_id,
                "stress_test_date": datetime.now().isoformat(),
                "scenarios": results,
                "summary": self._summarize_stress_test_results(results)
            }

            return result

        except Exception as e:
            logger.error(f"执行压力测试失败: {str(e)}")
            raise AnalysisException(f"执行压力测试失败: {str(e)}")

    def _get_strategy_returns(self, strategy_id: str, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """
        获取策略收益数据

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            策略收益数据列表
        """
        # TODO: 实现获取策略收益数据的逻辑
        # 这里返回模拟数据
        return [
            {"date": "2023-01-01", "return": 0.01},
            {"date": "2023-01-02", "return": -0.005},
            {"date": "2023-01-03", "return": 0.02},
        ]

    def _calculate_risk_metrics(self, returns_data: List[Dict[str, Any]],
                                 confidence_level: float, lookback_period: int) -> analysis_models.RiskMetrics:
        """
        计算风险指标

        Args:
            returns_data: 收益数据
            confidence_level: 置信水平
            lookback_period: 回看周期

        Returns:
            风险指标对象
        """
        # TODO: 实现具体的风险指标计算逻辑
        # 这里返回一个示例对象
        return analysis_models.RiskMetrics(
            portfolio_id="sample_portfolio",
            analysis_date=date.today(),
            confidence_level=Decimal(str(confidence_level)),
            historical_volatility=Decimal("0.18"),
            var_historical=Decimal("0.05"),
            var_parametric=Decimal("0.045"),
            conditional_var=Decimal("0.06")
        )

    def _get_portfolio_data(self, portfolio_id: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        获取投资组合数据

        Args:
            portfolio_id: 投资组合ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            投资组合数据
        """
        # TODO: 实现获取投资组合数据的逻辑
        return {"portfolio_id": portfolio_id, "assets": []}

    def _calculate_covariance_risk(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算协方差模型风险"""
        # TODO: 实现协方差模型风险计算
        return {"method": "covariance", "total_risk": 0.15}

    def _calculate_historical_risk(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算历史模拟风险"""
        # TODO: 实现历史模拟风险计算
        return {"method": "historical", "total_risk": 0.16}

    def _calculate_monte_carlo_risk(self, portfolio_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算蒙特卡洛模拟风险"""
        # TODO: 实现蒙特卡洛模拟风险计算
        return {"method": "monte_carlo", "total_risk": 0.14}

    def _get_portfolio_current_state(self, portfolio_id: str) -> Dict[str, Any]:
        """获取投资组合当前状态"""
        # TODO: 实现获取投资组合状态的逻辑
        return {"portfolio_id": portfolio_id, "positions": []}

    def _run_single_stress_test(self, portfolio_state: Dict[str, Any],
                                 scenario: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个压力测试场景"""
        # TODO: 实现压力测试逻辑
        scenario_name = scenario.get("name", "未知场景")
        return {
            "scenario_name": scenario_name,
            "portfolio_loss": -0.05,  # 模拟损失5%
            "affected_positions": [],
            "recommendations": ["考虑降低风险敞口"]
        }

    def _summarize_stress_test_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """汇总压力测试结果"""
        if not results:
            return {}

        max_loss = min(r.get("portfolio_loss", 0) for r in results)
        avg_loss = sum(r.get("portfolio_loss", 0) for r in results) / len(results)

        return {
            "max_portfolio_loss": max_loss,
            "average_portfolio_loss": avg_loss,
            "worst_case_scenario": min(results, key=lambda x: x.get("portfolio_loss", 0)).get("scenario_name"),
            "total_scenarios": len(results)
        }



# 风险分析适配器函数
async def get_strategy_risk_metrics(session: AsyncSession, strategy_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    获取策略风险指标 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = RiskAnalysisHandler(sync_session, user_id)
    return handler.get_strategy_risk_metrics(
        strategy_id=strategy_id,
        start_date=request.start_date,
        end_date=request.end_date,
        confidence_level=getattr(request, 'confidence_level', 0.95),
        lookback_period=getattr(request, 'lookback_period', 252)
    )

async def get_portfolio_risk(session: AsyncSession, portfolio_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    获取投资组合风险 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = RiskAnalysisHandler(sync_session, user_id)
    return handler.get_portfolio_risk(
        portfolio_id=portfolio_id,
        start_date=request.start_date,
        end_date=request.end_date,
        risk_model=getattr(request, 'risk_model', 'covariance')
    )

async def run_stress_test(session: AsyncSession, request, user_id: str) -> Dict[str, Any]:
    """
    执行压力测试 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = RiskAnalysisHandler(sync_session, user_id)
    return handler.run_stress_test(request.dict() if hasattr(request, 'dict') else request)


class ComparisonAnalysisHandler(BaseAnalysisHandler):
    """对比分析处理器"""

    def compare_strategies(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        对比多个策略

        Args:
            request: 策略对比请求

        Returns:
            策略对比结果
        """
        try:
            strategy_ids = request.get("strategy_ids", [])
            start_date = request.get("start_date")
            end_date = request.get("end_date")
            benchmark = request.get("benchmark")

            if not strategy_ids:
                raise AnalysisException("缺少策略ID列表")

            if len(strategy_ids) < 2:
                raise AnalysisException("至少需要2个策略进行对比")

            # 验证日期范围
            if not start_date or not end_date:
                today = date.today()
                end_date = today
                start_date = today - timedelta(days=365)
            else:
                start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取每个策略的数据
            strategies_data = []
            for strategy_id in strategy_ids:
                # 检查权限
                self._check_permission(strategy_id, "strategy")

                # 获取策略数据
                strategy_data = self._get_strategy_comparison_data(
                    strategy_id=strategy_id,
                    start_date=start_date,
                    end_date=end_date,
                    benchmark=benchmark
                )
                strategies_data.append(strategy_data)

            # 执行对比分析
            comparison_result = self._perform_comparison_analysis(
                strategies_data=strategies_data,
                start_date=start_date,
                end_date=end_date,
                benchmark=benchmark
            )

            # 构建响应
            result = {
                "comparison_id": f"comp_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "strategies": strategy_ids,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "benchmark": benchmark,
                "comparison_results": comparison_result
            }

            return result

        except Exception as e:
            logger.error(f"策略对比失败: {str(e)}")
            raise AnalysisException(f"策略对比失败: {str(e)}")

    def compare_with_benchmark(self, strategy_id: str, benchmark_code: str,
                                start_date: date, end_date: date) -> Dict[str, Any]:
        """
        与基准对比

        Args:
            strategy_id: 策略ID
            benchmark_code: 基准代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            基准对比结果
        """
        try:
            # 检查权限
            self._check_permission(strategy_id, "strategy")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取策略数据
            strategy_data = self._get_strategy_comparison_data(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date,
                benchmark=benchmark_code
            )

            # 获取基准数据
            benchmark_data = self._get_benchmark_data(
                benchmark_code=benchmark_code,
                start_date=start_date,
                end_date=end_date
            )

            if not benchmark_data:
                raise DataNotFoundException(f"基准数据不存在: {benchmark_code}")

            # 执行基准对比
            benchmark_comparison = self._perform_benchmark_comparison(
                strategy_data=strategy_data,
                benchmark_data=benchmark_data
            )

            # 构建响应
            result = {
                "strategy_id": strategy_id,
                "benchmark": benchmark_code,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "comparison_results": benchmark_comparison
            }

            return result

        except Exception as e:
            logger.error(f"基准对比失败: {str(e)}")
            raise AnalysisException(f"基准对比失败: {str(e)}")

    def analyze_correlation(self, item_ids: List[str], item_type: str,
                             start_date: date, end_date: date,
                             correlation_method: str = "pearson") -> Dict[str, Any]:
        """
        分析相关性

        Args:
            item_ids: 项目ID列表
            item_type: 项目类型 (strategy, asset, portfolio)
            start_date: 开始日期
            end_date: 结束日期
            correlation_method: 相关性计算方法

        Returns:
            相关性分析结果
        """
        try:
            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取每个项目的收益数据
            items_returns = []
            for item_id in item_ids:
                # 检查权限
                self._check_permission(item_id, item_type)

                # 获取项目收益数据
                if item_type == "strategy":
                    returns_data = self._get_strategy_returns_for_correlation(
                        strategy_id=item_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                elif item_type == "asset":
                    returns_data = self._get_asset_returns_for_correlation(
                        asset_id=item_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                elif item_type == "portfolio":
                    returns_data = self._get_portfolio_returns_for_correlation(
                        portfolio_id=item_id,
                        start_date=start_date,
                        end_date=end_date
                    )
                else:
                    raise AnalysisException(f"不支持的项目类型: {item_type}")

                items_returns.append({
                    "id": item_id,
                    "returns": returns_data
                })

            # 计算相关性矩阵
            correlation_matrix = self._calculate_correlation_matrix(
                items_returns=items_returns,
                method=correlation_method
            )

            # 进行聚类分析（可选）
            clustering_result = self._perform_clustering_analysis(correlation_matrix)

            # 构建响应
            result = {
                "item_ids": item_ids,
                "item_type": item_type,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "correlation_method": correlation_method,
                "correlation_matrix": correlation_matrix.to_dict() if hasattr(correlation_matrix, 'to_dict') else correlation_matrix,
                "clustering_analysis": clustering_result.to_dict() if hasattr(clustering_result, 'to_dict') else clustering_result,
                "recommendations": self._generate_correlation_recommendations(correlation_matrix)
            }

            return result

        except Exception as e:
            logger.error(f"相关性分析失败: {str(e)}")
            raise AnalysisException(f"相关性分析失败: {str(e)}")

    def _get_strategy_comparison_data(self, strategy_id: str, start_date: date,
                                      end_date: date, benchmark: Optional[str]) -> Dict[str, Any]:
        """获取策略对比数据"""
        # TODO: 实现获取策略对比数据的逻辑
        strategy = self.strategy_repo.get_by_id(strategy_id)
        return {
            "strategy_id": strategy_id,
            "strategy_name": strategy.name if strategy else strategy_id,
            "performance_metrics": {},
            "equity_curve": [],
            "risk_metrics": {}
        }

    def _get_benchmark_data(self, benchmark_code: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """获取基准数据"""
        # TODO: 实现获取基准数据的逻辑
        return {
            "benchmark_code": benchmark_code,
            "returns": [],
            "performance_metrics": {}
        }

    def _perform_comparison_analysis(self, strategies_data: List[Dict[str, Any]],
                                      start_date: date, end_date: date,
                                      benchmark: Optional[str]) -> Dict[str, Any]:
        """执行对比分析"""
        # TODO: 实现对比分析逻辑
        comparison_results = []
        for data in strategies_data:
            comparison_results.append({
                "strategy_id": data["strategy_id"],
                "total_return": 0.15,
                "annual_return": 0.12,
                "sharpe_ratio": 0.6,
                "max_drawdown": 0.08
            })

        return {
            "rankings": sorted(comparison_results, key=lambda x: x["sharpe_ratio"], reverse=True),
            "comparison_charts": {},
            "statistical_significance": {}
        }

    def _perform_benchmark_comparison(self, strategy_data: Dict[str, Any],
                                       benchmark_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行基准对比"""
        # TODO: 实现基准对比逻辑
        return {
            "outperformance": 0.02,  # 超额收益2%
            "correlation": 0.75,
            "tracking_error": 0.08,
            "information_ratio": 0.25
        }

    def _get_strategy_returns_for_correlation(self, strategy_id: str, start_date: date, end_date: date) -> List[float]:
        """获取策略收益率数据（用于相关性分析）"""
        # TODO: 实现获取策略收益率数据的逻辑
        return [0.01, -0.005, 0.02, 0.015, -0.003]

    def _get_asset_returns_for_correlation(self, asset_id: str, start_date: date, end_date: date) -> List[float]:
        """获取资产收益率数据（用于相关性分析）"""
        # TODO: 实现获取资产收益率数据的逻辑
        return [0.008, -0.002, 0.018, 0.012, -0.004]

    def _get_portfolio_returns_for_correlation(self, portfolio_id: str, start_date: date, end_date: date) -> List[float]:
        """获取投资组合收益率数据（用于相关性分析）"""
        # TODO: 实现获取投资组合收益率数据的逻辑
        return [0.009, -0.003, 0.019, 0.014, -0.002]

    def _calculate_correlation_matrix(self, items_returns: List[Dict[str, Any]], method: str) -> analysis_models.CorrelationMatrix:
        """计算相关性矩阵"""
        # TODO: 实现相关性矩阵计算逻辑
        import numpy as np

        # 模拟相关性矩阵计算
        n_items = len(items_returns)
        matrix = np.eye(n_items) * 0.5 + np.random.rand(n_items, n_items) * 0.5

        return analysis_models.CorrelationMatrix(
            matrix=matrix.tolist(),
            method=method,
            items=[item["id"] for item in items_returns]
        )

    def _perform_clustering_analysis(self, correlation_matrix: analysis_models.CorrelationMatrix) -> analysis_models.ClusteringResult:
        """执行聚类分析"""
        # TODO: 实现聚类分析逻辑
        return analysis_models.ClusteringResult(
            clusters=[{"items": ["item1", "item2"], "avg_correlation": 0.8}],
            dendrogram_data={},
            optimal_clusters=3
        )

    def _generate_correlation_recommendations(self, correlation_matrix: analysis_models.CorrelationMatrix) -> List[str]:
        """生成相关性分析建议"""
        # TODO: 实现相关性分析建议生成逻辑
        return [
            "考虑降低高度相关资产的风险敞口",
            "建议增加低相关性资产的配置"
        ]


# 对比分析适配器函数
async def compare_strategies(session: AsyncSession, request, user_id: str) -> Dict[str, Any]:
    """
    对比多个策略 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = ComparisonAnalysisHandler(sync_session, user_id)
    return handler.compare_strategies(request.dict() if hasattr(request, 'dict') else request)

async def compare_with_benchmark(session: AsyncSession, strategy_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    与基准对比 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = ComparisonAnalysisHandler(sync_session, user_id)
    return handler.compare_with_benchmark(
        strategy_id=strategy_id,
        benchmark_code=getattr(request, 'benchmark_code', '000300.SH'),  # 默认沪深300
        start_date=request.start_date,
        end_date=request.end_date
    )

async def analyze_correlation(session: AsyncSession, request, user_id: str) -> Dict[str, Any]:
    """
    分析相关性 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = ComparisonAnalysisHandler(sync_session, user_id)
    return handler.analyze_correlation(
        item_ids=getattr(request, 'item_ids', []),
        item_type=getattr(request, 'item_type', 'strategy'),
        start_date=request.start_date,
        end_date=request.end_date,
        correlation_method=getattr(request, 'correlation_method', 'pearson')
    )


class AttributionAnalysisHandler(BaseAnalysisHandler):
    """归因分析处理器"""

    def get_strategy_attribution(self, strategy_id: str, start_date: date,
                                  end_date: date, attribution_model: str = "brinson") -> Dict[str, Any]:
        """
        获取策略归因分析

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期
            attribution_model: 归因模型

        Returns:
            策略归因分析结果
        """
        try:
            # 检查权限
            self._check_permission(strategy_id, "strategy")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取策略数据
            strategy_data = self._get_strategy_attribution_data(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date
            )

            # 执行归因分析
            attribution_result = self._perform_attribution_analysis(
                strategy_data=strategy_data,
                model=attribution_model
            )

            # 构建响应
            result = {
                "strategy_id": strategy_id,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "attribution_model": attribution_model,
                "attribution_results": attribution_result
            }

            return result

        except Exception as e:
            logger.error(f"策略归因分析失败: {str(e)}")
            raise AnalysisException(f"策略归因分析失败: {str(e)}")

    def get_portfolio_attribution(self, portfolio_id: str, start_date: date,
                                   end_date: date, attribution_model: str = "brinson") -> Dict[str, Any]:
        """
        获取投资组合归因分析

        Args:
            portfolio_id: 投资组合ID
            start_date: 开始日期
            end_date: 结束日期
            attribution_model: 归因模型

        Returns:
            投资组合归因分析结果
        """
        try:
            # 检查权限
            self._check_permission(portfolio_id, "portfolio")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取投资组合数据
            portfolio_data = self._get_portfolio_attribution_data(
                portfolio_id=portfolio_id,
                start_date=start_date,
                end_date=end_date
            )

            # 执行归因分析
            attribution_result = self._perform_attribution_analysis(
                portfolio_data=portfolio_data,
                model=attribution_model
            )

            # 构建响应
            result = {
                "portfolio_id": portfolio_id,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "attribution_model": attribution_model,
                "attribution_results": attribution_result
            }

            return result

        except Exception as e:
            logger.error(f"投资组合归因分析失败: {str(e)}")
            raise AnalysisException(f"投资组合归因分析失败: {str(e)}")

    def _get_strategy_attribution_data(self, strategy_id: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """获取策略归因数据"""
        # TODO: 实现获取策略归因数据的逻辑
        return {
            "strategy_id": strategy_id,
            "positions": [],
            "trades": [],
            "returns": []
        }

    def _get_portfolio_attribution_data(self, portfolio_id: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """获取投资组合归因数据"""
        # TODO: 实现获取投资组合归因数据的逻辑
        return {
            "portfolio_id": portfolio_id,
            "positions": [],
            "trades": [],
            "returns": []
        }

    def _perform_attribution_analysis(self, data: Dict[str, Any], model: str) -> Dict[str, Any]:
        """执行归因分析"""
        # TODO: 实现归因分析逻辑
        return {
            "allocation_effect": 0.01,
            "selection_effect": 0.02,
            "interaction_effect": 0.003,
            "residual": 0.001,
            "total_attribution": 0.034
        }


# 归因分析适配器函数
async def get_strategy_attribution(session: AsyncSession, strategy_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    获取策略归因分析 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = AttributionAnalysisHandler(sync_session, user_id)
    return handler.get_strategy_attribution(
        strategy_id=strategy_id,
        start_date=request.start_date,
        end_date=request.end_date,
        attribution_model=getattr(request, 'attribution_model', 'brinson')
    )

async def get_portfolio_attribution(session: AsyncSession, portfolio_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    获取投资组合归因分析 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = AttributionAnalysisHandler(sync_session, user_id)
    return handler.get_portfolio_attribution(
        portfolio_id=portfolio_id,
        start_date=request.start_date,
        end_date=request.end_date,
        attribution_model=getattr(request, 'attribution_model', 'brinson')
    )


class TradeAnalysisHandler(BaseAnalysisHandler):
    """交易分析处理器"""

    def get_available_metrics(self, strategy_id, start_date, end_date):
        """
        获取可用指标列表

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            可用指标列表
        """
        try:
            # 检查权限
            self._check_permission(strategy_id, "strategy")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取可用的指标列表
            metrics = self._get_available_metrics_for_strategy(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date
            )

            return {
                "strategy_id": strategy_id,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "available_metrics": metrics
            }

        except Exception as e:
            logger.error(f"获取可用指标失败: {str(e)}")
            raise AnalysisException(f"获取可用指标失败: {str(e)}")

    def get_equity_curve(self, strategy_id, start_date, end_date, resolution="daily"):
        """
        获取净值曲线

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期
            resolution: 数据粒度 (daily, weekly, monthly)

        Returns:
            净值曲线数据
        """
        try:
            # 检查权限
            self._check_permission(strategy_id, "strategy")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 获取净值曲线数据
            equity_curve = self._get_equity_curve_data(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date,
                resolution=resolution
            )

            return {
                "strategy_id": strategy_id,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "resolution": resolution,
                "equity_curve": equity_curve
            }

        except Exception as e:
            logger.error(f"获取净值曲线失败: {str(e)}")
            raise AnalysisException(f"获取净值曲线失败: {str(e)}")

    def export_analysis_report(self, report_type, strategy_id, start_date, end_date, format="pdf"):
        """
        导出分析报告

        Args:
            report_type: 报告类型 (performance, risk, attribution)
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期
            format: 导出格式 (pdf, excel, html)

        Returns:
            报告导出结果
        """
        try:
            # 检查权限
            self._check_permission(strategy_id, "strategy")

            # 验证日期范围
            start_date, end_date = self._validate_date_range(start_date, end_date)

            # 生成报告
            report_data = self._generate_analysis_report(
                report_type=report_type,
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date,
                format=format
            )

            return {
                "report_id": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "report_type": report_type,
                "strategy_id": strategy_id,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "format": format,
                "report_url": report_data.get("url"),
                "file_size": report_data.get("size")
            }

        except Exception as e:
            logger.error(f"导出分析报告失败: {str(e)}")
            raise AnalysisException(f"导出分析报告失败: {str(e)}")

    def _get_available_metrics_for_strategy(self, strategy_id, start_date, end_date):
        """获取策略可用指标"""
        # TODO: 实现获取可用指标的逻辑
        return [
            {"id": "total_return", "name": "总收益率", "category": "performance"},
            {"id": "annual_return", "name": "年化收益率", "category": "performance"},
            {"id": "sharpe_ratio", "name": "夏普比率", "category": "risk_adjusted"},
            {"id": "max_drawdown", "name": "最大回撤", "category": "risk"}
        ]

    def _get_equity_curve_data(self, strategy_id, start_date, end_date, resolution):
        """获取净值曲线数据"""
        # TODO: 实现获取净值曲线数据的逻辑
        # 这里返回模拟数据
        return [
            {"date": "2024-01-01", "equity": 1000000, "return": 0.0},
            {"date": "2024-01-02", "equity": 1010000, "return": 0.01},
            {"date": "2024-01-03", "equity": 1005000, "return": -0.005}
        ]

    def _generate_analysis_report(self, report_type, strategy_id, start_date, end_date, format):
        """生成分析报告"""
        # TODO: 实现报告生成逻辑
        return {
            "url": f"/reports/{strategy_id}_{report_type}_{start_date}_{end_date}.{format}",
            "size": 1024000  # 1MB
        }


# 交易分析适配器函数
async def get_available_metrics(session: AsyncSession, strategy_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    获取可用指标列表 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = TradeAnalysisHandler(sync_session, user_id)
    return handler.get_available_metrics(
        strategy_id=strategy_id,
        start_date=request.start_date,
        end_date=request.end_date
    )

async def get_equity_curve(session: AsyncSession, strategy_id: str, request, user_id: str) -> Dict[str, Any]:
    """
    获取净值曲线 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = TradeAnalysisHandler(sync_session, user_id)
    return handler.get_equity_curve(
        strategy_id=strategy_id,
        start_date=request.start_date,
        end_date=request.end_date,
        resolution=getattr(request, 'resolution', 'daily')
    )

async def export_analysis_report(session: AsyncSession, request, user_id: str) -> Dict[str, Any]:
    """
    导出分析报告 - 顶层适配器函数
    """
    sync_session = session.sync_session if hasattr(session, 'sync_session') else Session.object_session(session)
    handler = TradeAnalysisHandler(sync_session, user_id)
    return handler.export_analysis_report(
        report_type=request.report_type,
        strategy_id=request.strategy_id,
        start_date=request.start_date,
        end_date=request.end_date,
        format=getattr(request, 'format', 'pdf')
    )


# 检查分析模块健康状态
async def check_analysis_module_health(session) -> Dict[str, Any]:
    """检查分析模块健康状态"""
    return {
        "status": "healthy",
        "module": "analysis",
        "timestamp": datetime.now().isoformat()
    }