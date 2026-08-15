# -*- coding: utf-8 -*-
"""
业务监控服务

无状态服务，聚合交易、账户、策略等业务指标。
被 BusinessMonitorEngine 调用。
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.repositories import OrderRepository, PositionRepository

logger = logging.getLogger(__name__)


class BusinessMonitorService:
	"""业务监控服务 — 无状态"""

	@staticmethod
	async def aggregate_metrics (
			start_date: Optional[datetime] = None,
			end_date: Optional[datetime] = None,
			session: Optional[AsyncSession] = None,
	) -> Dict[str, Any]:
		"""
		聚合业务指标

		从各业务 Repository 汇总关键指标。
		当前返回基础结构，后续可扩展接入具体 Repository。
		"""
		now = datetime.now(timezone.utc)
		if not end_date:
			end_date = now
		if not start_date:
			start_date = end_date - timedelta(days=30)

		metrics = {
			"period": {
				"start": start_date.isoformat(),
				"end": end_date.isoformat(),
			},
			"trading": {
				"total_orders": 0,
				"filled_orders": 0,
				"cancelled_orders": 0,
				"total_volume": 0.0,
				"total_turnover": 0.0,
			},
			"account": {
				"total_assets": 0.0,
				"available_cash": 0.0,
				"market_value": 0.0,
				"daily_pnl": 0.0,
				"cumulative_pnl": 0.0,
			},
			"strategy": {
				"active_strategies": 0,
				"total_signals": 0,
				"win_rate": 0.0,
				"avg_return": 0.0,
			},
			"timestamp": now.isoformat(),
		}

		# 尝试从数据库填充（若有 session）
		if session:
			try:
				await BusinessMonitorService._fill_from_repositories(metrics, session, start_date, end_date)
			except Exception as e:
				logger.warning(f"从数据库填充业务指标失败: {e}")

		return metrics

	@staticmethod
	async def _fill_from_repositories (
			metrics: Dict[str, Any],
			session: AsyncSession,
			start_date: datetime,
			end_date: datetime,
	) -> None:
		"""尝试从各 Repository 填充业务指标"""
		try:
			order_repo = OrderRepository(session)
			recent_orders = await order_repo.get_many(limit=1000)
			if recent_orders:
				metrics["trading"]["total_orders"] = len(recent_orders)
				filled = [o for o in recent_orders if getattr(o, 'status', None) == 'filled']
				cancelled = [o for o in recent_orders if getattr(o, 'status', None) == 'cancelled']
				metrics["trading"]["filled_orders"] = len(filled)
				metrics["trading"]["cancelled_orders"] = len(cancelled)
		except Exception:
			pass

		try:
			position_repo = PositionRepository(session)
			positions = await position_repo.get_many(limit=500)
			if positions:
				total_mv = sum(float(getattr(p, 'market_value', 0) or 0) for p in positions)
				total_pnl = sum(float(getattr(p, 'unrealized_pnl', 0) or 0) for p in positions)
				metrics["account"]["market_value"] = round(total_mv, 2)
				metrics["account"]["cumulative_pnl"] = round(total_pnl, 2)
		except Exception:
			pass
