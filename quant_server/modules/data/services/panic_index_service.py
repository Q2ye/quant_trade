# -*- coding: utf-8 -*-
"""
恐慌指数计算服务（无状态）

恐慌指数 = |全市场涨跌幅中位数(%)| × (下跌家数 / 总家数)
对应 `docs/00-核心策略体系/策略设计.md` §2.2 + M2 反例统计口径。
计算结果写入 panic_index 表（日频，trade_date 主键，upsert 幂等）。

数据来源：stock_daily（全市场日线，SQL 聚合，避免逐股遍历）
"""
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PanicIndexService:
	"""恐慌指数计算 — 无状态纯计算，不持有事件引擎引用"""

	@staticmethod
	async def recalculate(session: AsyncSession, start_date: date, end_date: date) -> int:
		"""计算并 upsert 指定日期范围的恐慌指数。

		Args:
			session: 数据库会话
			start_date / end_date: 计算区间（含边界）

		Returns:
			写入/更新的行数
		"""
		# 1. 全市场每日聚合：跌幅中位数 + 下跌家数/总家数
		result = await session.execute(text("""
			SELECT trade_date,
			       percentile_cont(0.5) WITHIN GROUP (ORDER BY pct_chg) AS median_pct_chg,
			       count(*) FILTER (WHERE pct_chg < 0) AS down_count,
			       count(*) AS total_count
			FROM stock_daily
			WHERE trade_date BETWEEN :s AND :e
			GROUP BY trade_date
			ORDER BY trade_date
		"""), {"s": start_date, "e": end_date})
		rows = result.fetchall()

		written = 0
		for row in rows:
			median = float(row.median_pct_chg or 0)
			total = int(row.total_count or 0)
			down = int(row.down_count or 0)
			if total <= 0:
				continue
			down_ratio = down / total
			# 恐慌指数：跌幅中位数取绝对值（普涨日中位数为正 → 0）
			panic_idx = max(0.0, -median) * down_ratio

			await session.execute(text("""
				INSERT INTO panic_index (trade_date, panic_idx, median_pct_chg, down_ratio)
				VALUES (:d, :p, :m, :r)
				ON CONFLICT (trade_date) DO UPDATE SET
					panic_idx = EXCLUDED.panic_idx,
					median_pct_chg = EXCLUDED.median_pct_chg,
					down_ratio = EXCLUDED.down_ratio
			"""), {
				"d": row.trade_date,
				"p": round(panic_idx, 4),
				"m": round(median, 4),
				"r": round(down_ratio, 4),
			})
			written += 1

		await session.commit()
		logger.info("恐慌指数已更新: %s ~ %s, %d 个交易日", start_date, end_date, written)
		return written

	@staticmethod
	async def get_latest(session: AsyncSession) -> Optional[Dict[str, Any]]:
		"""最新恐慌指数行（供策略/面板读取）。"""
		result = await session.execute(text(
			"SELECT trade_date, panic_idx FROM panic_index ORDER BY trade_date DESC LIMIT 1"
		))
		row = result.fetchone()
		if not row:
			return None
		return {"trade_date": row.trade_date, "panic_idx": float(row.panic_idx or 0)}

	@staticmethod
	async def get_range(session: AsyncSession, start_date: date, end_date: date) -> List[Dict[str, Any]]:
		"""区间恐慌指数序列（策略状态机读取）。"""
		result = await session.execute(text(
			"SELECT trade_date, panic_idx, median_pct_chg, down_ratio "
			"FROM panic_index WHERE trade_date BETWEEN :s AND :e ORDER BY trade_date"
		), {"s": start_date, "e": end_date})
		return [{
			"trade_date": row.trade_date,
			"panic_idx": float(row.panic_idx or 0),
			"median_pct_chg": float(row.median_pct_chg or 0),
			"down_ratio": float(row.down_ratio or 0),
		} for row in result.fetchall()]
