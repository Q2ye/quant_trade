# -*- coding: utf-8 -*-
"""
个股资金流数据仓库
位置：quant_server/shared/database/repositories/market/quote/stock_moneyflow_repo.py
职责：管理 stock_moneyflow 数据访问，提供「资金流强度」批量查询（net_mf_amount / circ_mv）。

约定：
  - 一表一仓库；不含业务逻辑，只做数据访问与单位换算。
  - `net_mf_amount`（万元）与 `daily_basic.circ_mv`（万元）同单位，比值无量纲。
  - `circ_mv <= 0` 或缺失的行**不返回**（调用方按缺失处理，fail-open）。
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import StockMoneyflow
from shared.database.repositories.base.hyper_repository_base import HyperRepositoryBase

logger = logging.getLogger(__name__)


class StockMoneyflowRepository(HyperRepositoryBase[StockMoneyflow]):
	"""个股资金流数据仓库（stock_moneyflow 为 TimescaleDB 超表）。"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, StockMoneyflow)
		self.time_column = "trade_date"

	async def get_mf_ratio_batch(
		self,
		symbols: List[str],
		start_date: date,
		end_date: date,
		limit: int = 2_000_000,
	) -> Dict[Tuple[str, str], float]:
		"""批量返回资金流强度 `net_mf_amount / circ_mv`。

		Args:
			symbols: 股票代码列表（TS 代码，如 600000.SH）。
			start_date / end_date: 日期闭区间。
			limit: 安全上限；超出时返回已取部分并告警（正常 5,000 只 × 1,400 日 ≈ 700 万）。

		Returns:
			{(ts_code, "YYYY-MM-DD"): ratio}；circ_mv 缺失或 <= 0 的键不出现。

		Raises:
			无。SQL 异常交由调用方处理（调用方需 catch 并降级为「无资金流」）。
		"""
		if not symbols:
			return {}

		query = text(
			"""
			SELECT m.ts_code,
			       m.trade_date,
			       m.net_mf_amount,
			       b.circ_mv
			FROM stock_moneyflow m
			LEFT JOIN daily_basic b
			       ON b.ts_code = m.ts_code AND b.trade_date = m.trade_date
			WHERE m.ts_code = ANY(:symbols)
			  AND m.trade_date BETWEEN :start AND :end
			ORDER BY m.trade_date, m.ts_code
			LIMIT :limit
			"""
		)
		result = await self.session.execute(
			query, {"symbols": symbols, "start": start_date, "end": end_date, "limit": limit}
		)
		rows: List[Any] = result.fetchall()
		if len(rows) >= limit:
			logger.warning(
				"stock_moneyflow 批量查询达到上限 %s 行，结果被截断（symbols=%s, %s~%s）",
				limit, len(symbols), start_date, end_date,
			)

		out: Dict[Tuple[str, str], float] = {}
		skipped = 0
		for r in rows:
			_mv: Optional[float] = float(r.circ_mv) if r.circ_mv is not None else None
			if _mv is None or _mv <= 0 or r.net_mf_amount is None:
				skipped += 1
				continue
			key = (r.ts_code, str(r.trade_date)[:10])
			out[key] = float(r.net_mf_amount) / _mv
		if skipped:
			logger.debug("资金流批量查询跳过 %s 行（circ_mv 或 net_mf_amount 缺失）", skipped)
		return out
