# -*- coding: utf-8 -*-
"""
复权价格生成工具

从 stock_daily + stock_adj_factor 计算前复权 OHLCV，写入 stock_adjusted_prices。
作为 sync_service 的补充模块，可独立调用或挂载到同步管线。
"""
import logging
from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def generate_adjusted_prices(
    session: AsyncSession,
    trade_date: Optional[date] = None,
    ts_codes: Optional[List[str]] = None,
    adj_type: str = "qfq",
    freq: str = "D",
) -> dict:
    """
    生成指定日期的前复权/后复权价格数据。

    算法：对每只股票，用 adj_factor 对 stock_daily 的 OHLCV 做复权。
    qfq (前复权): adjusted_price = raw_price * (current_factor / latest_factor)
    hfq (后复权): adjusted_price = raw_price / (current_factor / latest_factor)

    Args:
        session: 异步数据库会话
        trade_date: 交易日（默认昨日）
        ts_codes: 股票代码列表（None = 全部有日线数据的股票）
        adj_type: 复权类型 qfq/hfq
        freq: 频率 D/W/M

    Returns:
        {success, inserted_count, skipped_count, trade_date}
    """
    if trade_date is None:
        trade_date = date.today() - timedelta(days=1)

    logger.info(f"开始生成复权价格: trade_date={trade_date}, adj_type={adj_type}")

    # Step 1: 获取当日所有有日线数据的股票
    if ts_codes is None:
        daily_query = text(
            "SELECT DISTINCT ts_code FROM stock_daily WHERE trade_date = :trade_date"
        )
        result = await session.execute(daily_query, {"trade_date": trade_date})
        ts_codes = [r[0] for r in result.fetchall()]

    if not ts_codes:
        logger.info(f"无股票需要处理: {trade_date}")
        return {"success": True, "inserted_count": 0, "skipped_count": 0,
                "trade_date": str(trade_date)}

    # Step 2: 批量获取复权因子（最新因子 + 当日因子）
    # 获取每只股票的最新复权因子（作为基准）
    latest_factor_query = text("""
        SELECT af.ts_code, af.adj_factor
        FROM stock_adj_factor af
        INNER JOIN (
            SELECT ts_code, MAX(trade_date) AS max_date
            FROM stock_adj_factor
            WHERE ts_code = ANY(:ts_codes)
            GROUP BY ts_code
        ) latest ON af.ts_code = latest.ts_code AND af.trade_date = latest.max_date
    """)
    result = await session.execute(latest_factor_query, {"ts_codes": ts_codes})
    latest_factors = {r[0]: float(r[1]) for r in result.fetchall()}

    # 修复 2026-08（C2）：后复权需以最早因子为基准（旧实现用最新因子且除法，公式错误）
    earliest_factor_query = text("""
        SELECT af.ts_code, af.adj_factor
        FROM stock_adj_factor af
        INNER JOIN (
            SELECT ts_code, MIN(trade_date) AS min_date
            FROM stock_adj_factor
            WHERE ts_code = ANY(:ts_codes)
            GROUP BY ts_code
        ) earliest ON af.ts_code = earliest.ts_code AND af.trade_date = earliest.min_date
    """)
    result = await session.execute(earliest_factor_query, {"ts_codes": ts_codes})
    earliest_factors = {r[0]: float(r[1]) for r in result.fetchall()}

    # 获取当日复权因子
    current_factor_query = text(
        "SELECT ts_code, adj_factor FROM stock_adj_factor "
        "WHERE ts_code = ANY(:ts_codes) AND trade_date = :trade_date"
    )
    result = await session.execute(current_factor_query, {
        "ts_codes": ts_codes,
        "trade_date": trade_date,
    })
    current_factors = {r[0]: float(r[1]) for r in result.fetchall()}

    # Step 3: 批量获取日线数据
    daily_data_query = text(
        "SELECT ts_code, trade_date, open, high, low, close, vol, amount "
        "FROM stock_daily "
        "WHERE ts_code = ANY(:ts_codes) AND trade_date = :trade_date"
    )
    result = await session.execute(daily_data_query, {
        "ts_codes": ts_codes,
        "trade_date": trade_date,
    })
    daily_rows = {r[0]: r for r in result.fetchall()}

    # Step 4: 计算复权价格并批量写入
    from shared.database.repositories.market.quote.stock_adjusted_price_repo import (
        StockAdjustedPriceRepository,
    )

    repo = StockAdjustedPriceRepository(session)
    records = []
    skipped = 0

    for ts_code in ts_codes:
        row = daily_rows.get(ts_code)
        if not row:
            skipped += 1
            continue

        latest_factor = latest_factors.get(ts_code)
        current_factor = current_factors.get(ts_code)
        earliest_factor = earliest_factors.get(ts_code)

        if latest_factor is None or latest_factor <= 0:
            skipped += 1
            continue

        if current_factor is None or current_factor <= 0:
            # 当日无复权因子，跳过
            skipped += 1
            continue

        # 复权计算（修复 2026-08 C2）
        if adj_type == "qfq":
            # 前复权：以最新因子为基准，历史价 × (当日/最新)
            ratio = current_factor / latest_factor
            adj_open = float(row.open) * ratio if row.open else 0
            adj_high = float(row.high) * ratio if row.high else 0
            adj_low = float(row.low) * ratio if row.low else 0
            adj_close = float(row.close) * ratio if row.close else 0
        else:  # hfq
            # 后复权：以最早因子为基准，当日价 × (当日/最早)。
            # 旧实现 price / (当日/最新) 公式错误
            if earliest_factor and earliest_factor > 0:
                ratio = current_factor / earliest_factor
                adj_open = float(row.open) * ratio if row.open else 0
                adj_high = float(row.high) * ratio if row.high else 0
                adj_low = float(row.low) * ratio if row.low else 0
                adj_close = float(row.close) * ratio if row.close else 0
            else:
                skipped += 1
                continue

        records.append({
            "ts_code": ts_code,
            "trade_date": trade_date,
            "open": round(adj_open, 4),
            "high": round(adj_high, 4),
            "low": round(adj_low, 4),
            "close": round(adj_close, 4),
            "vol": float(row.vol) if row.vol else 0,
            "amount": float(row.amount) if row.amount else 0,
            "adj_type": adj_type,
            "freq": freq,
            "adj_factor": round(current_factor, 6),
            "asset_type": "E",  # E=股票
        })

    # 批量写入（upsert）
    inserted = 0
    if records:
        try:
            inserted = await repo.batch_upsert_adjusted_prices(records)
            await session.commit()
        except Exception as e:
            logger.error(f"批量写入复权价格失败: {e}")
            await session.rollback()
            raise

    logger.info(
        f"复权价格生成完成: trade_date={trade_date}, "
        f"inserted={inserted}, skipped={skipped}, total_stocks={len(ts_codes)}"
    )

    return {
        "success": True,
        "inserted_count": inserted,
        "skipped_count": skipped,
        "total_stocks": len(ts_codes),
        "trade_date": str(trade_date),
        "adj_type": adj_type,
    }
