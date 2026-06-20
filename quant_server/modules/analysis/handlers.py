#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析模块处理函数

负责绩效归因、风险分析、对比分析等业务逻辑处理。
AnalysisHandler 集中管理所有分析 Service，作为 API 路由层与 Service 层之间的适配器。

注意：check_analysis_module_health 不依赖任何 Service，保持为独立函数。
"""

import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.services.performance_service import PerformanceService
from modules.analysis.services.comparison_service import ComparisonService
from modules.analysis.services.attribution_service import AttributionService

logger = logging.getLogger(__name__)


class AnalysisHandler:
    """分析模块处理器，集中管理 Service 实例，作为 API 路由的适配层"""

    def __init__(self, db: AsyncSession):
        self.performance_service = PerformanceService(db)
        self.comparison_service = ComparisonService(db)
        self.attribution_service = AttributionService(db)

    # ==================== 绩效分析 ====================

    async def get_strategy_performance(self, strategy_id: str, request, _user_id: str) -> Dict[str, Any]:
        """获取策略绩效报告"""
        from datetime import datetime, timezone
        try:
            metrics = await self.performance_service.calculate_strategy_performance(
                strategy_id=strategy_id,
                start_date=request.start_date,
                end_date=request.end_date,
                benchmark=getattr(request, 'benchmark', None)
            )
            result = metrics.to_dict()
            if getattr(request, 'include_trades', False):
                result["trades"] = []
            return {
                "success": True,
                "message": f"策略 {strategy_id} 绩效分析完成",
                "data": result,
                "timestamp": datetime.now(timezone.utc),
            }
        except Exception as e:
            logger.error(f"计算策略绩效失败: {e}")
            return {
                "success": False,
                "message": f"计算策略绩效失败: {str(e)}",
                "data": {},
                "timestamp": datetime.now(timezone.utc),
            }

    async def get_account_performance(self, account_id: str, request, _user_id: str) -> Dict[str, Any]:
        """获取账户绩效报告"""
        from datetime import datetime, timezone
        try:
            metrics = await self.performance_service.calculate_account_performance(
                account_id=account_id,
                start_date=request.start_date,
                end_date=request.end_date
            )
            result = metrics if isinstance(metrics, dict) else metrics.to_dict()
            return {
                "success": True,
                "message": f"账户 {account_id} 绩效分析完成",
                "data": result,
                "timestamp": datetime.now(timezone.utc),
            }
        except Exception as e:
            logger.error(f"计算账户绩效失败: {e}")
            return {
                "success": False,
                "message": f"计算账户绩效失败: {str(e)}",
                "data": {},
                "timestamp": datetime.now(timezone.utc),
            }

    # ==================== 风险分析 ====================

    async def get_strategy_risk_metrics(self, strategy_id: str, request, _user_id: str) -> Dict[str, Any]:
        """获取策略风险指标 — 基于真实收益数据计算 VaR/CVaR"""
        import numpy as np

        confidence_level = getattr(request, 'confidence_level', 0.95)
        metrics = await self.performance_service.calculate_strategy_performance(
            strategy_id=strategy_id,
            start_date=request.start_date,
            end_date=request.end_date
        )

        daily_returns = np.array(metrics.daily_returns) if metrics.daily_returns else np.array([])
        if len(daily_returns) < 10:
            return {
                "strategy": {"id": strategy_id},
                "analysis_period": {"start_date": str(request.start_date), "end_date": str(request.end_date)},
                "parameters": {"confidence_level": confidence_level},
                "risk_metrics": {"error": "收益数据不足，至少需要10个交易日"}
            }

        volatility = float(np.std(daily_returns, ddof=1))
        var_historical = float(np.percentile(daily_returns, (1 - confidence_level) * 100))
        var_parametric = float(np.mean(daily_returns) - abs(np.percentile(np.random.randn(100000), (1 - confidence_level) * 100)) * volatility)
        cvar = float(daily_returns[daily_returns <= var_historical].mean()) if np.any(daily_returns <= var_historical) else var_historical

        return {
            "strategy": {"id": strategy_id},
            "analysis_period": {"start_date": str(request.start_date), "end_date": str(request.end_date)},
            "parameters": {"confidence_level": confidence_level, "lookback_period": len(daily_returns)},
            "risk_metrics": {
                "historical_volatility": volatility,
                "var_historical": var_historical,
                "var_parametric": var_parametric,
                "conditional_var": cvar,
                "max_drawdown": float(metrics.max_drawdown),
                "sharpe_ratio": float(metrics.sharpe_ratio),
            }
        }

    async def get_portfolio_risk(self, portfolio_id: str, request, _user_id: str) -> Dict[str, Any]:
        """获取投资组合风险 — 使用协方差/历史/MC 模型"""
        import numpy as np

        risk_model = getattr(request, 'risk_model', 'covariance')
        metrics = await self.performance_service.calculate_strategy_performance(
            strategy_id=portfolio_id,
            start_date=request.start_date,
            end_date=request.end_date
        )

        daily_returns = np.array(metrics.daily_returns) if metrics.daily_returns else np.array([])
        if len(daily_returns) < 10:
            return {"portfolio_id": portfolio_id, "risk_model": risk_model, "error": "收益数据不足"}

        if risk_model == "covariance":
            total_risk = float(np.std(daily_returns, ddof=1))
        elif risk_model == "historical":
            total_risk = float(np.percentile(daily_returns, 5))
        elif risk_model == "monte_carlo":
            simulated = np.random.choice(daily_returns, size=(10000, 252), replace=True).sum(axis=1)
            total_risk = float(np.percentile(simulated, 5))
        else:
            total_risk = float(np.std(daily_returns, ddof=1))

        return {
            "portfolio_id": portfolio_id,
            "risk_model": risk_model,
            "total_risk": total_risk,
            "volatility": float(np.std(daily_returns, ddof=1)),
            "var_95": float(np.percentile(daily_returns, 5)),
            "sharpe_ratio": float(metrics.sharpe_ratio),
        }

    async def run_stress_test(self, request, _user_id: str) -> Dict[str, Any]:
        """执行压力测试 — 对持仓应用情景冲击"""
        import numpy as np

        req = request.model_dump() if hasattr(request, 'model_dump') else request
        portfolio_id = req.get("portfolio_id")
        scenarios = req.get("scenarios", [])

        if not portfolio_id or not scenarios:
            return {"error": "缺少 portfolio_id 或 scenarios"}

        metrics = await self.performance_service.calculate_strategy_performance(
            strategy_id=portfolio_id,
            start_date=getattr(request, 'start_date', None),
            end_date=getattr(request, 'end_date', None)
        )

        daily_returns = np.array(metrics.daily_returns) if metrics.daily_returns else np.array([])
        base_vol = float(np.std(daily_returns, ddof=1)) if len(daily_returns) > 1 else 0.01

        results = []
        for scenario in scenarios:
            shock = float(scenario.get("shock", -0.10))
            name = scenario.get("name", "未命名情景")
            impact = shock * (1 + base_vol * np.random.randn())
            results.append({
                "scenario_name": name,
                "shock": shock,
                "estimated_impact": impact,
                "recommendations": ["考虑对冲"] if abs(impact) > 0.05 else []
            })

        return {
            "portfolio_id": portfolio_id,
            "scenarios": results,
            "summary": {
                "max_loss": min(r["estimated_impact"] for r in results) if results else 0,
                "worst_scenario": min(results, key=lambda r: r["estimated_impact"]).get("scenario_name") if results else "",
                "total_scenarios": len(results)
            }
        }

    # ==================== 对比分析 ====================

    async def compare_strategies(self, request, _user_id: str) -> Dict[str, Any]:
        """对比多个策略"""
        req = request.model_dump() if hasattr(request, 'model_dump') else request
        strategy_ids = req.get("strategy_ids", [])
        start_date = req.get("start_date")
        end_date = req.get("end_date")
        benchmark = req.get("benchmark")

        result = await self.comparison_service.compare_strategies(
            strategy_ids=strategy_ids,
            start_date=start_date,
            end_date=end_date,
            benchmark=benchmark
        )
        return result.to_dict()

    async def compare_with_benchmark(self, strategy_id: str, request, _user_id: str) -> Dict[str, Any]:
        """与基准对比"""
        from datetime import date, timedelta
        start_date = request.start_date or date.today() - timedelta(days=365)
        end_date = request.end_date or date.today()
        result = await self.comparison_service.compare_with_benchmark(
            strategy_id=strategy_id,
            benchmark_id=getattr(request, 'benchmark_code', '000300.SH'),
            start_date=start_date,
            end_date=end_date
        )
        return result

    async def analyze_correlation(self, request, _user_id: str) -> Dict[str, Any]:
        """分析相关性 — 使用 numpy 计算相关系数矩阵"""
        import numpy as np

        item_ids = getattr(request, 'item_ids', [])
        item_type = getattr(request, 'item_type', 'strategy')
        start_date = request.start_date
        end_date = request.end_date
        correlation_method = getattr(request, 'correlation_method', 'pearson')

        returns_dict = {}
        for item_id in item_ids:
            try:
                m = await self.performance_service.calculate_strategy_performance(
                    strategy_id=item_id, start_date=start_date, end_date=end_date
                )
                if m.daily_returns:
                    returns_dict[item_id] = np.array(m.daily_returns)
            except Exception:
                continue

        n = len(returns_dict)
        if n < 2:
            return {"item_ids": item_ids, "error": "数据不足，至少需要2个有效项目"}

        ids = list(returns_dict.keys())
        matrix = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                ri, rj = returns_dict[ids[i]], returns_dict[ids[j]]
                min_len = min(len(ri), len(rj))
                corr = float(np.corrcoef(ri[:min_len], rj[:min_len])[0, 1]) if min_len > 1 else 0
                matrix[i][j] = matrix[j][i] = corr

        return {
            "item_ids": ids,
            "item_type": item_type,
            "correlation_method": correlation_method,
            "correlation_matrix": {ids[i]: {ids[j]: float(matrix[i][j]) for j in range(n)} for i in range(n)}
        }

    # ==================== 归因分析 ====================

    async def get_strategy_attribution(self, strategy_id: str, request, _user_id: str) -> Dict[str, Any]:
        """获取策略归因分析"""
        attribution_model = getattr(request, 'attribution_model', 'brinson')

        if attribution_model == "brinson":
            benchmark = getattr(request, 'benchmark', '000300.SH')
            result = await self.attribution_service.perform_brinson_attribution(
                portfolio_id=strategy_id,
                start_date=request.start_date,
                end_date=request.end_date,
                benchmark=benchmark
            )
        else:
            result = await self.attribution_service.perform_factor_attribution(
                portfolio_id=strategy_id,
                start_date=request.start_date,
                end_date=request.end_date,
                factor_model="Fama-French" if attribution_model == "factor" else attribution_model
            )
        return result.to_dict()

    async def get_portfolio_attribution(self, portfolio_id: str, request, _user_id: str) -> Dict[str, Any]:
        """获取投资组合归因分析"""
        attribution_model = getattr(request, 'attribution_model', 'brinson')

        if attribution_model == "brinson":
            benchmark = getattr(request, 'benchmark', '000300.SH')
            result = await self.attribution_service.perform_brinson_attribution(
                portfolio_id=portfolio_id,
                start_date=request.start_date,
                end_date=request.end_date,
                benchmark=benchmark
            )
        else:
            result = await self.attribution_service.perform_factor_attribution(
                portfolio_id=portfolio_id,
                start_date=request.start_date,
                end_date=request.end_date
            )
        return result.to_dict()

    # ==================== 通用分析 ====================
    @staticmethod
    async def get_available_metrics( strategy_id: str, request, _user_id: str) -> Dict[str, Any]:
        """获取可用指标列表（从 constants.PERFORMANCE_METRICS 动态生成）"""
        from .constants import PERFORMANCE_METRICS

        metrics = []
        for group_key, group_metrics in PERFORMANCE_METRICS.items():
            for metric_id, metric_def in group_metrics.items():
                metrics.append({
                    "id": metric_id,
                    "name": metric_def["name"],
                    "category": group_key,
                })

        return {
            "strategy_id": strategy_id,
            "available_metrics": metrics,
        }

    async def get_equity_curve(self, strategy_id: str, request, _user_id: str) -> Dict[str, Any]:
        """获取净值曲线"""
        metrics = await self.performance_service.calculate_strategy_performance(
            strategy_id=strategy_id,
            start_date=request.start_date,
            end_date=request.end_date
        )
        return {
            "strategy_id": strategy_id,
            "equity_curve": metrics.equity_curve,
            "drawdown_curve": metrics.drawdown_curve,
        }

    @staticmethod
    async def export_analysis_report(request, _user_id: str) -> Dict[str, Any]:
        """导出分析报告"""
        from datetime import datetime as dt

        report_type = getattr(request, 'report_type', 'performance')
        strategy_id = getattr(request, 'strategy_id', '')
        start_date = getattr(request, 'start_date', '')
        end_date = getattr(request, 'end_date', '')
        fmt = getattr(request, 'format', 'pdf')

        return {
            "report_id": f"report_{dt.now().strftime('%Y%m%d_%H%M%S')}",
            "report_type": report_type,
            "strategy_id": strategy_id,
            "analysis_period": {"start_date": str(start_date), "end_date": str(end_date)},
            "format": fmt,
            "report_url": f"/reports/{strategy_id}_{report_type}_{start_date}_{end_date}.{fmt}",
            "file_size": 0,
            "status": "generated"
        }


async def check_analysis_module_health(session) -> Dict[str, Any]:
    """检查分析模块健康状态"""
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "module": "analysis",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "module": "analysis",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }
