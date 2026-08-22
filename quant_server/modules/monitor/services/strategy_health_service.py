# -*- coding: utf-8 -*-
"""
策略健康度监控服务（无状态）

对应 `docs/00-核心策略体系/基建设计.md` §三（策略失效监控）。
对每个运行中的策略进行月度体检，输出 healthy / warning / stop 分级 + 预警原因。

数据来源（只读，复用现有 Repository）：
- strategies（运行中策略清单）        → StrategyRepository.get_active_strategies()
- strategy_daily_performance（实盘净值） → StrategyDailyPerformanceRepository
- signals（信号频率）                → SignalRepository.get_by_time_range()
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories.account.asset.strategy_daily_performance_repo import (
    StrategyDailyPerformanceRepository,
)
from shared.database.repositories.strategy.management.strategy_repo import (
    StrategyRepository,
)
from shared.database.repositories.strategy.signal.signal_repo import (
    SignalRepository,
)

logger = logging.getLogger(__name__)


class StrategyHealthService:
	"""策略健康度检查 — 无状态纯计算，不持有事件引擎引用"""

	@staticmethod
	async def check_all(session: AsyncSession, months: int = 3) -> List[Dict[str, Any]]:
		"""检查所有运行中策略的健康状态。"""
		strategy_repo = StrategyRepository(session)
		active = await strategy_repo.get_active_strategies()
		results = []
		for s in active:
			results.append(await StrategyHealthService._analyze(s, session, months))
		return results

	@staticmethod
	async def check_strategy_health(
			session: AsyncSession,
			strategy_id: str,
			months: int = 3,
	) -> Dict[str, Any]:
		"""检查单个策略的健康状态。"""
		strategy_repo = StrategyRepository(session)
		strategy = await strategy_repo.get_by_id(strategy_id)
		if strategy is None:
			return {"strategy_id": strategy_id, "name": "未知策略", "status": "not_found",
			        "alerts": ["策略不存在"], "metrics": {}}
		return await StrategyHealthService._analyze(strategy, session, months)

	# ------------------------------------------------------------------
	@staticmethod
	async def _analyze(strategy, session: AsyncSession, months: int) -> Dict[str, Any]:
		"""核心判定：近 N 月表现 vs 历史基准 + 失效规则（基建设计 §3.3）。"""
		strategy_id = str(getattr(strategy, "id", ""))
		name = str(getattr(strategy, "name", strategy_id))
		alerts: List[str] = []
		status = "healthy"

		perf_repo = StrategyDailyPerformanceRepository(session)
		signal_repo = SignalRepository(session)

		now = datetime.now()
		recent_start = (now - timedelta(days=months * 31)).date()
		hist_start = (now - timedelta(days=months * 31 * 3)).date()

		recent = await perf_repo.get_strategy_performance(strategy_id, recent_start, now.date())
		history = await perf_repo.get_strategy_performance(strategy_id, hist_start, recent_start)

		metrics: Dict[str, Any] = {
			"recent_days": len(recent),
			"history_days": len(history),
			"recent_return": 0.0,
			"recent_mdd": 0.0,
			"hist_avg_return": None,
			"hist_max_mdd": None,
			"recent_signal_count": 0,
			"hist_monthly_signal_avg": None,
		}

		# ---- 样本不足保护 ----
		if not recent:
			return {"strategy_id": strategy_id, "name": name, "status": "insufficient",
			        "alerts": ["近 {} 个月无实盘绩效数据".format(months)], "metrics": metrics}
		if len(recent) < 20:
			return {"strategy_id": strategy_id, "name": name, "status": "insufficient",
			        "alerts": ["样本积累中（{} 个交易日）".format(len(recent))], "metrics": metrics}

		# ---- 近段指标 ----
		recent_sorted = sorted(recent, key=lambda p: p.trade_date)
		start_cr = float(recent_sorted[0].total_return or 0)
		end_cr = float(recent_sorted[-1].total_return or 0)
		metrics["recent_return"] = round((end_cr - start_cr) / (1 + start_cr) if (1 + start_cr) != 0 else 0.0, 6)
		metrics["recent_mdd"] = round(max(float(p.max_drawdown or 0) for p in recent), 6)

		# 近段月度收益（按月聚合 daily_return 求和）
		monthly: Dict[str, float] = {}
		for p in recent:
			m = p.trade_date.strftime("%Y-%m")
			monthly[m] = monthly.get(m, 0.0) + float(p.daily_return or 0)
		month_returns = [monthly[k] for k in sorted(monthly)]

		# ---- 历史基准 ----
		if history:
			hist_sorted = sorted(history, key=lambda p: p.trade_date)
			hist_returns = []
			hist_months: Dict[str, float] = {}
			for p in hist_sorted:
				hist_returns.append(float(p.daily_return or 0))
				m = p.trade_date.strftime("%Y-%m")
				hist_months[m] = hist_months.get(m, 0.0) + float(p.daily_return or 0)
			metrics["hist_avg_return"] = round(
				sum(hist_returns) / len(hist_returns) if hist_returns else 0.0, 6)
			metrics["hist_max_mdd"] = round(max(float(p.max_drawdown or 0) for p in hist_sorted), 6)
			hist_monthly_avg = (
				sum(hist_months.values()) / len(hist_months) if hist_months else 0.0)
		else:
			hist_monthly_avg = None

		# ---- 信号频率 ----
		recent_sigs = await signal_repo.get_by_time_range(
			start_time=now - timedelta(days=months * 31), end_time=now,
			strategy_ids=[strategy_id],
		)
		metrics["recent_signal_count"] = len(recent_sigs)
		hist_sigs = await signal_repo.get_by_time_range(
			start_time=now - timedelta(days=months * 31 * 3),
			end_time=now - timedelta(days=months * 31),
			strategy_ids=[strategy_id],
		)
		if hist_sigs:
			metrics["hist_monthly_signal_avg"] = round(len(hist_sigs) / (months * 2), 2)

		# ==================== 判定（基建设计 §3.3） ====================
		# ---- 停用级（stop） ----
		if metrics["recent_mdd"] > 0.30:
			# 创新高判定：近段 MDD 是否超过历史最大
			if metrics["hist_max_mdd"] is None or metrics["recent_mdd"] > metrics["hist_max_mdd"]:
				alerts.append("最大回撤创新高且 > 30%")
				status = "stop"

		# 连续 6 个月净值不创新高（近 6 月 total_return 峰值未突破历史峰值）
		hist_peak = max((float(p.total_return or 0) for p in history), default=-999.0)
		recent_peak = max(float(p.total_return or 0) for p in recent)
		if history and recent_peak <= hist_peak and len(recent_sorted) >= 120:
			alerts.append("连续 6 个月净值不创新高")
			if status != "stop":
				status = "stop"

		# 近 1 年收益 < 0（取近 12 月 total_return 首尾差）
		year_ago = (now - timedelta(days=365)).date()
		year_perf = await perf_repo.get_strategy_performance(strategy_id, year_ago, now.date())
		if year_perf:
			ys = sorted(year_perf, key=lambda p: p.trade_date)
			y_start = float(ys[0].total_return or 0)
			y_end = float(ys[-1].total_return or 0)
			year_ret = (y_end - y_start) / (1 + y_start) if (1 + y_start) != 0 else 0.0
			if year_ret < 0 and len(ys) >= 60:
				alerts.append("最近 1 年收益 < 0")
				if status != "stop":
					status = "stop"

		# ---- 预警级（warning，仅在非 stop 时叠加） ----
		if status != "stop":
			# 连续 3 个月负收益（样本不足 3 个月时跳过）
			consec_neg = 0
			for r in month_returns:
				consec_neg = consec_neg + 1 if r < 0 else 0
			if len(month_returns) >= 3 and consec_neg >= 3:
				alerts.append("连续 {} 个月负收益".format(consec_neg))
				status = "warning"

			# 近 N 月收益 < 历史同期 1/2（按月均比较）
			if hist_monthly_avg is not None and len(month_returns) >= months:
				recent_monthly_avg = sum(month_returns) / len(month_returns)
				if recent_monthly_avg < hist_monthly_avg * 0.5:
					alerts.append("近 {} 个月收益低于历史同期 1/2".format(months))
					status = "warning"

			# 近 N 月 MDD > 历史 MDD 的 80%
			if metrics["hist_max_mdd"] and metrics["hist_max_mdd"] > 0 and metrics["recent_mdd"] > metrics["hist_max_mdd"] * 0.8:
				alerts.append("近 {} 个月最大回撤超历史 80%".format(months))
				status = "warning"

			# 信号频率偏差 > 2x
			if metrics["hist_monthly_signal_avg"] is not None and metrics["hist_monthly_signal_avg"] > 0:
				recent_monthly_sig = metrics["recent_signal_count"] / max(len(month_returns), 1)
				if recent_monthly_sig > metrics["hist_monthly_signal_avg"] * 2 or \
				   recent_monthly_sig < metrics["hist_monthly_signal_avg"] * 0.5:
					alerts.append("信号频率异常（近 {} 个月 vs 历史均值偏差 > 2x）".format(months))
					status = "warning"

		if not alerts:
			alerts = ["策略健康"]

		return {
			"strategy_id": strategy_id,
			"name": name,
			"status": status,
			"alerts": alerts,
			"metrics": metrics,
		}
